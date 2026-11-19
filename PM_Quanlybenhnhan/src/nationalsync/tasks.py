"""
Celery task for the national health portal sync — Phase 8, Sprint 16.

``sync_checkup_data`` runs the full push pipeline asynchronously so the admin
does not block on a network call to EMRHUB:

    login → resolve examinations → (skip already synced) → per-exam push
"""

from __future__ import annotations

import base64
import json
import logging

from celery import shared_task
from django.utils import timezone

from nationalsync import services, xml_builder
from nationalsync.models import SyncConfig, SyncJob
from nationalsync.scope import resolve_examinations, successfully_synced_ids

logger = logging.getLogger(__name__)


@shared_task
def sync_checkup_data(job_id: str) -> dict[str, int]:
    """Execute one sync job end-to-end and persist per-exam results."""
    try:
        job = SyncJob.objects.select_related("company", "patient").get(pk=job_id)
    except SyncJob.DoesNotExist:
        logger.error("SyncJob %s not found", job_id)
        return {"synced": 0, "failed": 0, "skipped": 0}

    job.status = SyncJob.STATUS_PROCESSING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])

    success_ids: list[str] = []
    failures: list[dict[str, str]] = []
    skipped = 0

    try:
        config = SyncConfig.load(job.environment)
        if not config.is_active:
            raise services.EmrHubError("Đồng bộ đang tắt (is_active=False).")
        if not config.is_configured:
            raise services.EmrHubError("Chưa cấu hình đầy đủ SyncConfig.")

        examinations = list(
            resolve_examinations(
                job.scope_type,
                company_id=job.company_id,
                patient_id=job.patient_id,
                examination_id=job.examination_id,
            )
            .select_related("patient", "patient__company", "doctor")
            .prefetch_related(
                "department_results__department", "department_results__values"
            )
        )
        if not examinations:
            raise services.EmrHubError("Không có lượt khám nào trong phạm vi đã chọn.")

        job.examination_count = len(examinations)
        job.save(update_fields=["examination_count", "updated_at"])

        # Bulk "sync all" skips exams already pushed successfully for this env.
        # Explicit single-exam jobs always re-push.
        already = (
            set()
            if job.examination_id
            else successfully_synced_ids(job.environment)
        )
        pending = []
        for exam in examinations:
            if str(exam.id) in already:
                skipped += 1
            else:
                pending.append(exam)

        if not pending:
            job.response = {
                "message": "Tất cả lượt khám trong phạm vi đã đồng bộ trước đó.",
                "skipped": skipped,
            }
            job.status = SyncJob.STATUS_DONE
            job.error_message = ""
            job.success_count = 0
            job.failed_count = 0
            job.skipped_count = skipped
            job.synced_examination_ids = []
        else:
            token = services.login(config)
            responses: dict[str, object] = {}

            for exam in pending:
                exam_key = str(exam.id)
                try:
                    try:
                        stored = json.loads(job.cks_nguoi_ket_luan or "{}")
                    except json.JSONDecodeError:
                        stored = {}
                    signatures = (
                        stored.get("signatures") if isinstance(stored, dict) else {}
                    )
                    documents = stored.get("xml") if isinstance(stored, dict) else {}
                    doctor_signature = ""
                    unsigned_xml = ""
                    if isinstance(signatures, dict):
                        doctor_signature = str(signatures.get(exam_key) or "")
                    if isinstance(documents, dict):
                        unsigned_xml = str(documents.get(exam_key) or "")
                    patient_type = xml_builder.resolve_emrhub_type(
                        exam.patient, on_date=exam.exam_date
                    )
                    if unsigned_xml and doctor_signature:
                        xml_str = xml_builder.embed_facility_signature(
                            unsigned_xml, doctor_signature
                        )
                        data_b64 = base64.b64encode(xml_str.encode("utf-8")).decode(
                            "ascii"
                        )
                    else:
                        data_b64 = xml_builder.build_data_b64(
                            [exam],
                            config,
                            facility_signature=doctor_signature or None,
                            ngay_lap=timezone.localdate(),
                        )
                    header = services.build_header(config)
                    signature = services.sign_payload(
                        header, data_b64, config.private_key
                    )
                    responses[exam_key] = services.push_data(
                        config,
                        token,
                        header,
                        data_b64,
                        signature,
                        patient_type=patient_type,
                    )
                    success_ids.append(exam_key)
                except Exception as exc:
                    logger.exception(
                        "National sync job %s failed for examination %s",
                        job_id,
                        exam_key,
                    )
                    failures.append(
                        {
                            "examination_id": exam_key,
                            "patient": getattr(exam.patient, "full_name", "") or "",
                            "error": str(exc),
                        }
                    )

            job.response = {
                "results": responses,
                "failures": failures,
                "skipped": skipped,
            }
            job.success_count = len(success_ids)
            job.failed_count = len(failures)
            job.skipped_count = skipped
            job.synced_examination_ids = success_ids

            if failures and not success_ids:
                job.status = SyncJob.STATUS_FAILED
                job.error_message = _summarize_failures(failures)
            elif failures:
                job.status = SyncJob.STATUS_DONE
                job.error_message = (
                    f"Đồng bộ một phần: {len(success_ids)} thành công, "
                    f"{len(failures)} thất bại. {_summarize_failures(failures)}"
                )
            else:
                job.status = SyncJob.STATUS_DONE
                job.error_message = ""
    except Exception as exc:
        logger.exception("National sync job %s failed", job_id)
        job.status = SyncJob.STATUS_FAILED
        job.error_message = str(exc)
        job.success_count = len(success_ids)
        job.failed_count = max(job.failed_count, len(failures)) or (
            0 if success_ids else job.examination_count
        )
        job.skipped_count = skipped
        if success_ids:
            job.synced_examination_ids = success_ids
    finally:
        job.completed_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "response",
                "error_message",
                "examination_count",
                "success_count",
                "failed_count",
                "skipped_count",
                "synced_examination_ids",
                "completed_at",
                "updated_at",
            ]
        )

    return {
        "synced": job.success_count,
        "failed": job.failed_count,
        "skipped": job.skipped_count,
    }


def _summarize_failures(failures: list[dict[str, str]], *, limit: int = 3) -> str:
    parts = [
        f"{item.get('patient') or item.get('examination_id')}: {item.get('error', '')}"
        for item in failures[:limit]
    ]
    extra = len(failures) - limit
    text = "; ".join(parts)
    if extra > 0:
        text = f"{text}; … và {extra} lỗi khác"
    return text
