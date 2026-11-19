"""
Tests for the national health portal sync — Phase 8, Sprint 16.

Covers:
  * SyncConfig singleton + secret masking
  * header building (msg_id, send_datetime)
  * RSA-SHA256 signature (verified against the public key)
  * KHAMSUCKHOE XML structure (7 FILEHOSO blocks)
  * scope resolution + pre-sync validation
  * admin-only API access + validate/trigger endpoints
"""

from __future__ import annotations

import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import date
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Company, CompanyExamPackage
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
)
from nationalsync import services, xml_builder
from nationalsync.mapping import extract_mapping_fields
from nationalsync.models import (
    SyncConfig,
    SyncFieldMapping,
    SyncJob,
    SyncMappingVersion,
)
from nationalsync.scope import resolve_examinations, validate_scope
from nationalsync.serializers import SyncConfigSerializer
from patients.models import Patient

User = get_user_model()


def _make_user(role: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{role}@nsync.test")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _make_rsa_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


class SyncConfigTests(APITestCase):
    def test_load_returns_default_when_empty(self) -> None:
        config = SyncConfig.load()
        self.assertIsInstance(config, SyncConfig)
        self.assertEqual(config.environment, SyncConfig.ENV_SANDBOX)

    def test_effective_api_base_url_derives_from_environment(self) -> None:
        config = SyncConfig.objects.create(
            environment=SyncConfig.ENV_PRODUCTION,
            username="u",
            password="p",
            sender_id="8934285091236",
            private_key="k",
        )
        self.assertEqual(config.effective_api_base_url, "https://api.emrhub.vn")
        config.environment = SyncConfig.ENV_SANDBOX
        self.assertEqual(config.effective_api_base_url, "https://api-sandbox.emrhub.vn")

    def test_api_base_url_override_wins(self) -> None:
        config = SyncConfig.objects.create(api_base_url="https://custom.example")
        self.assertEqual(config.effective_api_base_url, "https://custom.example")

    def test_api_base_url_without_scheme_gets_https(self) -> None:
        config = SyncConfig.objects.create(api_base_url="api-sandbox.emrhub.vn")
        self.assertEqual(config.effective_api_base_url, "https://api-sandbox.emrhub.vn")

    def test_api_base_url_trailing_slash_stripped(self) -> None:
        config = SyncConfig.objects.create(api_base_url="https://api.emrhub.vn/")
        self.assertEqual(config.effective_api_base_url, "https://api.emrhub.vn")

    def test_serializer_masks_secrets(self) -> None:
        config = SyncConfig.objects.create(
            username="agent",
            password="secret-pass",
            sender_id="8934285091236",
            private_key="-----BEGIN PRIVATE KEY-----...",
        )
        data = SyncConfigSerializer(config).data
        self.assertNotIn("password", data)
        self.assertNotIn("private_key", data)
        self.assertTrue(data["password_set"])
        self.assertTrue(data["private_key_set"])
        self.assertTrue(data["is_configured"])


class HeaderAndSignTests(APITestCase):
    def test_build_msg_id_format(self) -> None:
        msg_id = services.build_msg_id("8934285091236")
        self.assertTrue(msg_id.startswith("8934285091236"))
        self.assertNotIn("-", msg_id)

    def test_build_header_has_required_fields_in_order(self) -> None:
        config = SyncConfig(sender_id="8934285091236", version="1.0.6")
        header = services.build_header(config)
        self.assertEqual(
            list(header.keys()),
            [
                "version",
                "sender_id",
                "receiver_id",
                "txn_type",
                "msg_type",
                "data_type",
                "send_datetime",
                "msg_id",
            ],
        )
        self.assertEqual(header["txn_type"], "sync_checkup")
        self.assertEqual(header["msg_type"], "101")
        self.assertEqual(header["data_type"], "xml/base64")
        self.assertGreaterEqual(len(str(header["send_datetime"])), 13)

    def test_sign_payload_verifies_against_public_key(self) -> None:
        private_pem, public_pem = _make_rsa_keys()
        header = {
            "version": "1.0.6",
            "sender_id": "8934285091236",
            "receiver_id": "TTYQG",
            "txn_type": "sync_checkup",
            "msg_type": "101",
            "data_type": "xml/base64",
            "send_datetime": 1781084650736,
            "msg_id": "89342850912362607169",
        }
        data = "<KHAMSUCKHOE />\n"
        signature = services.sign_payload(header, data, private_pem)

        public_key = serialization.load_pem_public_key(public_pem.encode())

        header_sha = (
            hashlib.sha256(
                json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode()
            )
            .hexdigest()
            .upper()
        )
        data_sha = hashlib.sha256(data.strip().encode()).hexdigest().upper()
        public_key.verify(
            base64.b64decode(signature),
            f"{header_sha}.{data_sha}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )


class XmlBuilderTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = Company.objects.create(name="Công ty TNHH ABC", code="ABC")
        cls.patient = Patient.objects.create(
            company=cls.company,
            employee_code="E1",
            full_name="NGUYỄN VĂN A",
            dob=date(1990, 1, 1),
            gender="M",
            cccd="893812613317",
            address="Số 1, An Giang",
            phone="0912345678",
        )
        cls.exam = Examination.objects.create(
            patient=cls.patient,
            exam_type="periodic",
            exam_date=date(2026, 7, 9),
            status="confirmed",
            classification=2,
            conclusion="Đủ sức khỏe làm việc",
            disease="Không phát hiện bệnh lý cấp tính",
        )

        cls.clinical = Department.objects.create(
            name="Khám lâm sàng", code="kham_lam_sang_ns", category="clinical"
        )
        cls.physical = Department.objects.create(
            name="Khám thể lực", code="the_luc_ns", category="clinical"
        )
        cls.lab = Department.objects.create(
            name="Xét nghiệm máu", code="xet_nghiem_mau_ns", category="para_clinical"
        )
        cls.template = DepartmentTemplate.objects.create(
            department=cls.lab, name="XN máu"
        )

        physical_result = DepartmentResult.objects.create(
            examination=cls.exam,
            department=cls.physical,
            template_snapshot=[],
        )
        physical_result._sync_values(
            {"chieu_cao": 168, "can_nang": 60, "mach": 78, "huyet_ap": "120/80"}
        )

        lab_result = DepartmentResult.objects.create(
            examination=cls.exam,
            department=cls.lab,
            template=cls.template,
            template_snapshot=[
                {"key": "hemoglobin", "label": "Huyết sắc tố", "unit": "g/L"},
            ],
        )
        lab_result._sync_values({"hemoglobin": 130})

    def test_xml_has_seven_file_hoso_blocks(self) -> None:
        config = SyncConfig(
            sender_id="8934285091236", facility_code="01816", version="1.0.6"
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<KHAMSUCKHOE", xml)
        self.assertIn("<MACSKCB>8934285091236</MACSKCB>", xml)
        self.assertIn("<SOLUONGHOSO>1</SOLUONGHOSO>", xml)
        for loai in ["XML1", "XML2", "XML7", "XML9", "XML10", "XML11", "XML12"]:
            self.assertIn(f"<LOAIHOSO>{loai}</LOAIHOSO>", xml)

    def test_xml1_maps_patient(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<HO_TEN>NGUYỄN VĂN A</HO_TEN>", xml)
        self.assertIn("<GIOI_TINH>1</GIOI_TINH>", xml)
        self.assertIn("<SO_CCCD>893812613317</SO_CCCD>", xml)
        self.assertIn(
            "<NOI_LAM_VIEC_HOC_TAP>Công ty TNHH ABC</NOI_LAM_VIEC_HOC_TAP>", xml
        )
        self.assertIn("<MATINH_CU_TRU>91</MATINH_CU_TRU>", xml)
        self.assertNotIn("<MA_NGHE_NGHIEP>", xml)
        self.assertIn("<LY_DO_VV>Khám sức khỏe định kỳ</LY_DO_VV>", xml)
        self.assertNotIn("<TUAN_THAI>", xml)
        self.assertIn("<MA_DAN_TOC>01</MA_DAN_TOC>", xml)
        self.assertNotIn("<NGUON_CHI_TRA>", xml)
        self.assertNotIn("<MA_LOAI_KCB>", xml)

    def test_xml1_ma_dan_toc_uses_patient_override_when_present(self) -> None:
        self.patient.ethnicity_code = "02"  # type: ignore[attr-defined]
        try:
            config = SyncConfig(sender_id="8934285091236")
            xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
            self.assertIn("<MA_DAN_TOC>02</MA_DAN_TOC>", xml)
        finally:
            del self.patient.ethnicity_code  # type: ignore[attr-defined]

    def test_xml1_ma_nghe_nghiep_uses_patient_override_when_present(self) -> None:
        self.patient.occupation_code = "2151"  # type: ignore[attr-defined]
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<MA_NGHE_NGHIEP>2151</MA_NGHE_NGHIEP>", xml)

    def test_xml1_matinh_from_address_variants(self) -> None:
        from nationalsync.provinces import resolve_admin_codes, resolve_province_code

        self.assertEqual(resolve_province_code("Số 1, Xã An Minh, An Giang"), "91")
        self.assertEqual(resolve_province_code("Tỉnh An Giang"), "91")
        self.assertEqual(resolve_province_code("TP. Hồ Chí Minh"), "79")
        self.assertEqual(resolve_province_code("Hà Nội"), "01")
        self.assertEqual(resolve_province_code("Thừa Thiên Huế"), "46")
        self.assertEqual(resolve_province_code("Đắk Lắk"), "66")
        self.assertEqual(resolve_province_code(""), "")
        self.assertEqual(resolve_province_code("không rõ"), "")

        self.assertEqual(
            resolve_admin_codes("Số 1, Xã An Minh, An Giang"),
            ("91", "31018"),
        )
        self.assertEqual(resolve_admin_codes("Tỉnh An Giang"), ("91", ""))
        self.assertEqual(
            resolve_admin_codes("Phường Hoàn Kiếm, Hà Nội"),
            ("01", "00070"),
        )
        self.assertEqual(
            resolve_admin_codes("Xã Tân Tiến, Thanh Hóa"),
            ("38", "16108"),
        )
        self.assertEqual(
            resolve_admin_codes("Xã Tân Thành, Tây Ninh"),
            ("80", "25534"),
        )
        self.assertEqual(
            resolve_admin_codes("Xã Tân Thạnh, Tây Ninh"),
            ("80", "27826"),
        )
        # Same folded spelling in one province — do not guess.
        self.assertEqual(resolve_admin_codes("Xa Tan Thanh, Tay Ninh"), ("80", ""))
        # Name shared by several provinces, and no province in the address.
        self.assertEqual(resolve_admin_codes("Xã Tân Tiến"), ("", ""))
        # Unique nationwide, so the province can be inferred.
        self.assertEqual(resolve_admin_codes("Xã An Minh"), ("91", "31018"))

    def test_xml1_includes_commune_code(self) -> None:
        original = self.patient.address
        self.patient.address = "Số 1, Xã An Minh, An Giang"
        config = SyncConfig(sender_id="8934285091236")
        try:
            xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        finally:
            self.patient.address = original
        self.assertIn("<MATINH_CU_TRU>91</MATINH_CU_TRU>", xml)
        self.assertIn("<MAXA_CU_TRU>31018</MAXA_CU_TRU>", xml)

    def test_xml_includes_doctor_png_as_base64(self) -> None:
        from accounts.signatures import store_signature_image

        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        doctor = User.objects.create_user(
            email="cks-doctor@nsync.test",
            password="TestPass123!",
            full_name="Bác sĩ Kết luận",
            role="doctor",
        )
        store_signature_image(doctor, png)
        self.exam.doctor = doctor
        self.exam.save(update_fields=["doctor"])
        try:
            config = SyncConfig(sender_id="8934285091236")
            xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        finally:
            self.exam.doctor = None
            doctor.signature_image.delete(save=False)
        self.assertIn("<CKS_NGUOI_KET_LUAN />", xml)
        self.assertIn("<CKS_BENH_VIEN />", xml)

    def test_xml_uses_stored_base64_when_no_image(self) -> None:
        doctor = User.objects.create_user(
            email="cks-b64@nsync.test",
            password="TestPass123!",
            full_name="Bác sĩ Base64",
            role="doctor",
        )
        doctor.signature_base64 = base64.b64encode(b"token-sig").decode()
        doctor.save(update_fields=["signature_base64"])
        self.exam.doctor = doctor
        self.exam.save(update_fields=["doctor"])
        try:
            config = SyncConfig(sender_id="8934285091236")
            xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        finally:
            self.exam.doctor = None
        self.assertIn("<CKS_NGUOI_KET_LUAN />", xml)
        self.assertNotIn(doctor.signature_base64, xml)

    def test_xml_includes_facility_signature_when_configured(self) -> None:
        from nationalsync.models import FacilitySignature

        facility = FacilitySignature.load()
        facility.signature_base64 = base64.b64encode(b"benh-vien").decode()
        facility.save(update_fields=["signature_base64"])
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn(
            f"<CKS_BENH_VIEN>{facility.signature_base64}</CKS_BENH_VIEN>",
            xml,
        )

    def test_xml_uses_usb_token_signature_when_supplied(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        token_sig = base64.b64encode(b"cms-signature").decode()
        xml = xml_builder.build_kham_suc_khoe_xml(
            [self.exam], config, facility_signature=token_sig
        )
        self.assertIn(f"<CKS_BENH_VIEN>{token_sig}</CKS_BENH_VIEN>", xml)
        self.assertIn("<CKS_NGUOI_KET_LUAN />", xml)

    def test_embed_doctor_signature_keeps_the_rest_of_the_document(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml(
            [self.exam], config, facility_signature=""
        )
        signed = xml_builder.embed_facility_signature(xml, "QUJD")
        self.assertIn("<CKS_BENH_VIEN>QUJD</CKS_BENH_VIEN>", signed)
        self.assertIn("<CKS_NGUOI_KET_LUAN />", signed)
        self.assertEqual(
            signed.replace(
                "<CKS_BENH_VIEN>QUJD</CKS_BENH_VIEN>",
                "<CKS_BENH_VIEN />",
            ),
            xml,
        )

    def test_require_chuky_signatures_accepts_usb_without_stored_image(self) -> None:
        doctor = User.objects.create_user(
            email="cks-usb-only@nsync.test",
            password="TestPass123!",
            full_name="BS USB",
            role="doctor",
        )
        self.exam.doctor = doctor
        self.exam.save(update_fields=["doctor"])
        try:
            xml_builder.require_chuky_signatures(
                [self.exam],
                doctor_signature=base64.b64encode(b"cms-signature").decode(),
            )
        finally:
            self.exam.doctor = None

    def test_require_chuky_signatures_allows_missing_facility(self) -> None:
        from nationalsync.models import FacilitySignature

        facility = FacilitySignature.objects.filter(pk=1).first()
        if facility is not None:
            facility.signature_base64 = ""
            if facility.signature_image:
                facility.signature_image.delete(save=False)
            facility.save()
        doctor = User.objects.create_user(
            email="cks-no-facility@nsync.test",
            password="TestPass123!",
            full_name="BS Không BV",
            role="doctor",
        )
        doctor.signature_base64 = base64.b64encode(b"bs").decode()
        doctor.save(update_fields=["signature_base64"])
        self.exam.doctor = doctor
        self.exam.save(update_fields=["doctor"])
        try:
            xml_builder.require_chuky_signatures([self.exam])
        finally:
            self.exam.doctor = None
            self.exam.save(update_fields=["doctor"])

    def test_require_chuky_signatures_ok_when_both_present(self) -> None:
        from nationalsync.models import FacilitySignature

        doctor = User.objects.create_user(
            email="cks-ready@nsync.test",
            password="TestPass123!",
            full_name="BS Ready",
            role="doctor",
        )
        doctor.signature_base64 = base64.b64encode(b"bs").decode()
        doctor.save(update_fields=["signature_base64"])
        facility = FacilitySignature.load()
        facility.signature_base64 = base64.b64encode(b"bv").decode()
        facility.save(update_fields=["signature_base64"])
        self.exam.doctor = doctor
        self.exam.save(update_fields=["doctor"])
        try:
            xml_builder.require_chuky_signatures([self.exam])
        finally:
            self.exam.doctor = None
            self.exam.save(update_fields=["doctor"])

    def test_xml10_maps_physical_fields(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<CHIEU_CAO>168</CHIEU_CAO>", xml)
        self.assertIn("<HUYET_AP>120/80</HUYET_AP>", xml)

    def test_xml11_maps_paraclinical_fields(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<TEN_CHI_SO>Huyết sắc tố</TEN_CHI_SO>", xml)
        self.assertIn("<GIA_TRI>130</GIA_TRI>", xml)

    def test_xml12_maps_conclusion(self) -> None:
        config = SyncConfig(sender_id="8934285091236")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<PHAN_LOAI_SK>2</PHAN_LOAI_SK>", xml)
        self.assertIn(
            "<CAC_VAN_DE_SUC_KHOE>Đủ sức khỏe làm việc</CAC_VAN_DE_SUC_KHOE>", xml
        )

    def test_xml2_includes_emrhub_type_adult(self) -> None:
        config = SyncConfig(sender_id="8934285091236", facility_code="01816")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)
        self.assertIn("<TYPE>Adult</TYPE>", xml)

    def test_empty_xml_tags_are_omitted_from_push_document(self) -> None:
        """Optional empty data leaves are omitted; schema placeholders stay.

        EMRHUB sample keeps ``CHUKYDONVI`` empty; stripping it caused
        ``ERROR_99`` / Unknown error on push.
        """
        config = SyncConfig(sender_id="8934285091236", facility_code="01816")
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], config)

        # Optional patient/CLS fields with no value → omit.
        for empty_tag in (
            "NHOM_MAU",
            "NGUOI_GIAM_HO",
            "MA_DICH_VU",
            "MO_TA",
            "KET_LUAN_BENH",
        ):
            self.assertNotIn(f"<{empty_tag}>", xml)
            self.assertNotIn(f"<{empty_tag}/>", xml)

        # No sample-XML filler defaults (MA_NGHE_NGHIEP=04, TUAN_THAI=0, …).
        self.assertNotIn("<MA_NGHE_NGHIEP>", xml)
        self.assertNotIn("<TUAN_THAI>", xml)
        self.assertIn("<LY_DO_VV>Khám sức khỏe định kỳ</LY_DO_VV>", xml)

        # Signature block preserved (empty) like the official sample.
        # ElementTree writes an empty element as a self-closing tag.
        self.assertIn("<CHUKYDONVI>", xml)
        self.assertIn("<CKS_NGUOI_KET_LUAN />", xml)
        self.assertIn("<CKS_BENH_VIEN />", xml)

        # Empty leaf under CHI_TIET_CLS (not the XML12 wrapper <KET_LUAN>).
        self.assertNotIn("<KET_LUAN></KET_LUAN>", xml)
        self.assertNotIn("<KET_LUAN/>", xml)
        self.assertIn("<KET_LUAN>", xml)  # XML12 block root still present

        # Populated fields must remain; sample zeros must not.
        self.assertIn("<HO_TEN>NGUYỄN VĂN A</HO_TEN>", xml)
        self.assertIn("<GIA_TRI>130</GIA_TRI>", xml)

    def test_strip_empty_elements_preserves_chukydonvi(self) -> None:
        root = ET.Element("KHAMSUCKHOE")
        keep = ET.SubElement(root, "KEEP")
        keep.text = "x"
        chu_ky = ET.SubElement(root, "CHUKYDONVI")
        ET.SubElement(chu_ky, "CKS_NGUOI_KET_LUAN")
        ET.SubElement(chu_ky, "CKS_BENH_VIEN")
        empty = ET.SubElement(root, "OPTIONAL_EMPTY")
        empty.text = ""
        xml_builder.strip_empty_elements(root)
        tags = [c.tag for c in root]
        self.assertEqual(tags, ["KEEP", "CHUKYDONVI"])
        self.assertEqual(len(chu_ky), 2)

    def test_resolve_emrhub_type_by_age(self) -> None:
        from datetime import date as d

        class P:
            def __init__(self, dob):
                self.dob = dob

        on = d(2026, 9, 6)
        self.assertEqual(
            xml_builder.resolve_emrhub_type(P(d(2022, 1, 1)), on_date=on),
            "ChildUnder",
        )
        self.assertEqual(
            xml_builder.resolve_emrhub_type(P(d(2012, 1, 1)), on_date=on),
            "Minor",
        )
        self.assertEqual(
            xml_builder.resolve_emrhub_type(P(d(1990, 1, 1)), on_date=on),
            "Adult",
        )
        self.assertEqual(
            xml_builder.resolve_emrhub_type(P(None), on_date=on),
            "Adult",
        )


class ScopeAndValidationTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = Company.objects.create(name="Cty", code="SYNC")
        cls.patient = Patient.objects.create(
            company=cls.company, employee_code="E1", full_name="Nguyễn Văn A"
        )
        cls.walkin = Patient.objects.create(full_name="Bệnh nhân lẻ")
        cls.package = ExamPackage.objects.create(name="KSK", exam_type="periodic")
        cls.cep = CompanyExamPackage.objects.create(
            company=cls.company, exam_package=cls.package, pricing_mode="per_field"
        )
        cls.exam_completed = Examination.objects.create(
            patient=cls.patient,
            company_exam_package=cls.cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 1),
            status="completed",
        )
        cls.exam_draft = Examination.objects.create(
            patient=cls.patient,
            company_exam_package=cls.cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 2),
            status="draft",
        )
        cls.walkin_exam = Examination.objects.create(
            patient=cls.walkin,
            exam_type="periodic",
            exam_date=date(2026, 1, 1),
            status="confirmed",
        )

    def test_resolve_company_scope(self) -> None:
        qs = resolve_examinations("company", company_id=self.company.id)
        self.assertEqual(qs.count(), 2)

    def test_resolve_company_scope_excludes_exams_without_active_package(self) -> None:
        # Exam linked to the company's patient but WITHOUT an active
        # CompanyExamPackage must be excluded (not part of an active gói khám).
        Examination.objects.create(
            patient=self.patient,
            exam_type="periodic",
            exam_date=date(2026, 1, 3),
            status="completed",
        )
        qs = resolve_examinations("company", company_id=self.company.id)
        self.assertEqual(qs.count(), 2)

    def test_resolve_company_scope_excludes_inactive_package(self) -> None:
        inactive_pkg = ExamPackage.objects.create(name="KSK cũ", exam_type="periodic")
        inactive_cep = CompanyExamPackage.objects.create(
            company=self.company,
            exam_package=inactive_pkg,
            pricing_mode="per_field",
            is_active=False,
        )
        Examination.objects.create(
            patient=self.patient,
            company_exam_package=inactive_cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 3),
            status="completed",
        )
        qs = resolve_examinations("company", company_id=self.company.id)
        self.assertEqual(qs.count(), 2)

    def test_resolve_patient_scope(self) -> None:
        qs = resolve_examinations("patient", patient_id=self.walkin.id)
        self.assertEqual(qs.count(), 1)

    def test_validate_includes_draft_examinations(self) -> None:
        result = validate_scope("company", company_id=self.company.id)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["eligible"], 2)
        self.assertEqual(result["incomplete"], [])
        statuses = {row["status"] for row in result["eligible_exams"]}
        self.assertEqual(statuses, {"draft", "completed"})

    def test_validate_all_eligible(self) -> None:
        result = validate_scope("patient", patient_id=self.walkin.id)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["incomplete"], [])
        self.assertEqual(result["already_synced_count"], 0)
        self.assertEqual(len(result["eligible_exams"]), 1)
        self.assertIn("signature_issues", result)
        self.assertFalse(any("CKS_BENH_VIEN" in msg for msg in result["signature_issues"]))
        self.assertFalse(any("Chữ ký số" in msg for msg in result["signature_issues"]))

    def test_resolve_single_examination(self) -> None:
        qs = resolve_examinations(
            "company",
            company_id=self.company.id,
            examination_id=self.exam_completed.id,
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.get().id, self.exam_completed.id)

    def test_validate_single_eligible_examination(self) -> None:
        result = validate_scope(
            "company",
            company_id=self.company.id,
            examination_id=self.exam_completed.id,
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["incomplete"], [])
        self.assertEqual(result["eligible_exams"][0]["id"], str(self.exam_completed.id))


def _xmldsig_for(*exam_ids: object) -> dict[str, str]:
    xml = '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#" Id="sample"></Signature>'
    token = base64.b64encode(xml.encode("utf-8")).decode("ascii")
    return {str(exam_id): token for exam_id in exam_ids}


class SyncApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin = _make_user("admin", email="admin@api.test")
        cls.doctor = _make_user("doctor", email="doctor@api.test")
        cls.company = Company.objects.create(name="Cty", code="API")
        cls.patient = Patient.objects.create(
            company=cls.company, employee_code="E1", full_name="Nguyễn Văn A"
        )
        cls.package = ExamPackage.objects.create(name="KSK", exam_type="periodic")
        cls.cep = CompanyExamPackage.objects.create(
            company=cls.company, exam_package=cls.package, pricing_mode="per_field"
        )
        cls.exam = Examination.objects.create(
            patient=cls.patient,
            company_exam_package=cls.cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 1),
            status="completed",
        )

    def test_non_admin_forbidden(self) -> None:
        self.client.force_authenticate(self.doctor)
        resp = self.client.get("/api/sync/config/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_config_roundtrip_masks_secrets(self) -> None:
        self.client.force_authenticate(self.admin)
        resp = self.client.put(
            "/api/sync/config/",
            {
                "environment": "sandbox",
                "username": "agent",
                "password": "secret",
                "sender_id": "8934285091236",
                "private_key": "-----BEGIN PRIVATE KEY-----",
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_configured"])
        self.assertNotIn("password", resp.data)
        self.assertNotIn("private_key", resp.data)

    def test_validate_endpoint_allows_draft(self) -> None:
        Examination.objects.create(
            patient=self.patient,
            company_exam_package=self.cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 2),
            status="draft",
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/validate/",
            {"scope_type": "company", "company_id": str(self.company.id)},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["incomplete"], [])
        self.assertEqual(resp.data["eligible"], 2)

    @patch("nationalsync.views.sync_checkup_data.delay")
    def test_trigger_creates_job_when_valid(self, mock_delay) -> None:
        SyncConfig.objects.create(
            environment="sandbox",
            username="agent",
            password="p",
            sender_id="8934285091236",
            private_key="k",
            is_active=True,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/trigger/",
            {
                "scope_type": "company",
                "company_id": str(self.company.id),
                "cks_nguoi_ket_luan": _xmldsig_for(self.exam.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["status"], SyncJob.STATUS_PENDING)
        mock_delay.assert_called_once()
        self.assertEqual(SyncJob.objects.count(), 1)

    @patch("nationalsync.views.sync_checkup_data.delay")
    def test_trigger_allows_draft_examinations(self, mock_delay) -> None:
        draft = Examination.objects.create(
            patient=self.patient,
            company_exam_package=self.cep,
            exam_type="periodic",
            exam_date=date(2026, 1, 2),
            status="draft",
        )
        SyncConfig.objects.create(
            environment="sandbox",
            username="agent",
            password="p",
            sender_id="8934285091236",
            private_key="k",
            is_active=True,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/trigger/",
            {
                "scope_type": "company",
                "company_id": str(self.company.id),
                "cks_nguoi_ket_luan": _xmldsig_for(self.exam.id, draft.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_delay.assert_called_once()
        self.assertEqual(SyncJob.objects.get().examination_count, 2)

    @patch("nationalsync.views.sync_checkup_data.delay")
    def test_trigger_skips_already_synced_on_bulk(self, mock_delay) -> None:
        SyncConfig.objects.create(
            environment="sandbox",
            username="agent",
            password="p",
            sender_id="8934285091236",
            private_key="k",
            is_active=True,
        )
        SyncJob.objects.create(
            environment="sandbox",
            scope_type="company",
            company=self.company,
            examination=self.exam,
            status=SyncJob.STATUS_DONE,
            synced_examination_ids=[str(self.exam.id)],
            success_count=1,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/trigger/",
            {
                "scope_type": "company",
                "company_id": str(self.company.id),
                "environment": "sandbox",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("đã đồng bộ", resp.data["detail"].lower())
        mock_delay.assert_not_called()

    @patch("nationalsync.views.sync_checkup_data.delay")
    def test_trigger_single_exam_allows_resync(
        self, mock_delay
    ) -> None:
        SyncConfig.objects.create(
            environment="sandbox",
            username="agent",
            password="p",
            sender_id="8934285091236",
            private_key="k",
            is_active=True,
        )
        SyncJob.objects.create(
            environment="sandbox",
            scope_type="company",
            company=self.company,
            examination=self.exam,
            status=SyncJob.STATUS_DONE,
            synced_examination_ids=[str(self.exam.id)],
            success_count=1,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/trigger/",
            {
                "scope_type": "company",
                "company_id": str(self.company.id),
                "examination_id": str(self.exam.id),
                "environment": "sandbox",
                "cks_nguoi_ket_luan": _xmldsig_for(self.exam.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_delay.assert_called_once()
        job = SyncJob.objects.latest("created_at")
        self.assertEqual(job.examination_id, self.exam.id)
        self.assertEqual(job.examination_count, 1)

    @patch("nationalsync.views.sync_checkup_data.delay")
    def test_trigger_uses_selected_environment(self, mock_delay) -> None:
        SyncConfig.objects.create(
            environment="production",
            username="agent",
            password="p",
            sender_id="8934285091236",
            private_key="k",
            is_active=True,
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            "/api/sync/trigger/",
            {
                "environment": "production",
                "scope_type": "company",
                "company_id": str(self.company.id),
                "cks_nguoi_ket_luan": _xmldsig_for(self.exam.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["environment"], "production")
        mock_delay.assert_called_once()
        self.assertEqual(SyncJob.objects.get().environment, "production")

    def test_config_get_returns_both_environments(self) -> None:
        SyncConfig.objects.create(
            environment="sandbox", username="sandbox_user", is_active=True
        )
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/sync/config/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("sandbox", resp.data)
        self.assertIn("production", resp.data)
        self.assertEqual(resp.data["sandbox"]["environment"], "sandbox")
        self.assertEqual(resp.data["production"]["environment"], "production")


class FacilitySignatureApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin", email="facility-admin@nsync.test")
        self.doctor = _make_user("doctor", email="facility-doctor@nsync.test")

    def tearDown(self) -> None:
        from nationalsync.models import FacilitySignature

        facility = FacilitySignature.objects.filter(pk=1).first()
        if facility is not None and facility.signature_image:
            facility.signature_image.delete(save=False)

    def test_admin_saves_base64_and_can_clear_it(self) -> None:
        self.client.force_authenticate(self.admin)
        empty = self.client.get("/api/sync/facility-signature/")
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertEqual(empty.data["signature_kind"], "")

        saved = self.client.put(
            "/api/sync/facility-signature/",
            {"signature_base64": base64.b64encode(b"bv").decode()},
            format="json",
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(saved.data["signature_kind"], "base64")

        cleared = self.client.delete("/api/sync/facility-signature/")
        self.assertEqual(cleared.status_code, status.HTTP_204_NO_CONTENT)
        again = self.client.get("/api/sync/facility-signature/")
        self.assertEqual(again.data["signature_kind"], "")

    def test_doctor_cannot_configure_facility_signature(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.get("/api/sync/facility-signature/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SyncFieldMappingTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin", email="map-admin@nsync.test")
        self.doctor = _make_user("doctor", email="map-doctor@nsync.test")
        self.clinical = Department.objects.create(
            name="Khám lâm sàng", code="ls_map", category="clinical"
        )
        self.other = Department.objects.create(
            name="Xét nghiệm map", code="xn_map", category="para_clinical"
        )
        template = DepartmentTemplate.objects.create(
            department=self.clinical, name="Mẫu lâm sàng"
        )
        DepartmentField.objects.create(
            template=template, key="chieu_cao", label="Chiều cao"
        )
        company = Company.objects.create(name="Cty Map", code="MAP1")
        patient = Patient.objects.create(
            company=company,
            employee_code="M1",
            full_name="NGUYỄN VĂN MAP",
            dob=date(1990, 1, 1),
            gender="M",
        )
        self.exam = Examination.objects.create(
            patient=patient,
            exam_type="periodic",
            exam_date=date(2026, 7, 9),
            status="confirmed",
        )
        self.config = SyncConfig(sender_id="8934285091236")
        self.version = SyncMappingVersion.objects.create(
            name="Mẫu",
            is_default=True,
            extracted_fields=[
                {
                    "block": "xml10",
                    "tag": "CHIEU_CAO",
                    "label": "Chiều cao",
                    "ma_dich_vu": "",
                    "ma_chi_so": "",
                },
                {
                    "block": "xml10",
                    "tag": "CAN_NANG",
                    "label": "Cân nặng",
                    "ma_dich_vu": "",
                    "ma_chi_so": "",
                },
                {
                    "block": "xml11",
                    "tag": "",
                    "label": "Huyết sắc tố",
                    "ma_dich_vu": "03C3.1.89",
                    "ma_chi_so": "H02",
                },
            ],
        )

    def _result(self, department: Department, data: dict) -> DepartmentResult:
        result = DepartmentResult.objects.create(
            examination=self.exam,
            department=department,
            template_snapshot=[
                {"key": key, "label": key, "unit": "cm"} for key in data
            ],
        )
        result._sync_values(data)
        return result

    def test_admin_can_save_mapping_doctor_cannot(self) -> None:
        self.client.force_authenticate(self.admin)
        created = self.client.post(
            "/api/sync/field-mappings/",
            {
                "version": str(self.version.id),
                "block": "xml10",
                "xml_tag": "CHIEU_CAO",
                "department": str(self.clinical.id),
                "field_key": "chieu_cao",
                "alias_keys": ["cao"],
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        self.assertTrue(created.data["field_present"])

        self.client.force_authenticate(self.doctor)
        forbidden = self.client.get("/api/sync/field-mappings/")
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        forbidden_write = self.client.post(
            "/api/sync/field-mappings/",
            {
                "block": "xml10",
                "xml_tag": "CAN_NANG",
                "department": str(self.clinical.id),
                "field_key": "can_nang",
            },
            format="json",
        )
        self.assertEqual(forbidden_write.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(self.admin)
        updated = self.client.put(
            f"/api/sync/field-mappings/{created.data['id']}/",
            {
                "version": str(self.version.id),
                "block": "xml10",
                "xml_tag": "CHIEU_CAO",
                "department": str(self.clinical.id),
                "field_key": "chieu_cao",
                "alias_keys": ["cao", "height"],
            },
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK, updated.data)
        self.assertEqual(updated.data["alias_keys"], ["cao", "height"])

    def test_mapped_clinical_key_fills_xml10(self) -> None:
        self._result(self.clinical, {"chieu_cao": 170})
        SyncFieldMapping.objects.create(
            version=self.version,
            block="xml10",
            xml_tag="CHIEU_CAO",
            department=self.clinical,
            field_key="chieu_cao",
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertIn("<CHIEU_CAO>170</CHIEU_CAO>", xml)

    def test_missing_department_falls_back_to_same_key(self) -> None:
        self._result(self.other, {"chieu_cao": 165})
        SyncFieldMapping.objects.create(
            version=self.version,
            block="xml10",
            xml_tag="CHIEU_CAO",
            department=self.clinical,
            field_key="chieu_cao",
            alias_keys=["cao"],
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertIn("<CHIEU_CAO>165</CHIEU_CAO>", xml)

    def test_empty_configured_department_does_not_use_another_value(self) -> None:
        self._result(self.clinical, {"note": "ổn"})
        self._result(self.other, {"chieu_cao": 165})
        SyncFieldMapping.objects.create(
            version=self.version,
            block="xml10",
            xml_tag="CHIEU_CAO",
            department=self.clinical,
            field_key="chieu_cao",
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertNotIn("<CHIEU_CAO>", xml)

    def test_xml11_mapping_uses_ministry_codes(self) -> None:
        self._result(self.other, {"hemoglobin": 130})
        SyncFieldMapping.objects.create(
            version=self.version,
            block="xml11",
            department=self.other,
            field_key="hemoglobin",
            ma_dich_vu="03C3.1.89",
            ma_chi_so="H02",
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertIn("<MA_DICH_VU>03C3.1.89</MA_DICH_VU>", xml)
        self.assertIn("<MA_CHI_SO>H02</MA_CHI_SO>", xml)
        self.assertIn("<GIA_TRI>130</GIA_TRI>", xml)

    def test_only_the_default_version_is_used(self) -> None:
        self._result(self.clinical, {"chieu_cao": 170})
        self.version.is_default = False
        self.version.save(update_fields=["is_default"])
        SyncFieldMapping.objects.create(
            version=self.version,
            block="xml10",
            xml_tag="CHIEU_CAO",
            department=self.clinical,
            field_key="chieu_cao",
        )
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertNotIn("<CHIEU_CAO>", xml)

        self.version.activate()
        xml = xml_builder.build_kham_suc_khoe_xml([self.exam], self.config)
        self.assertIn("<CHIEU_CAO>170</CHIEU_CAO>", xml)


_SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<KHAMSUCKHOE>
  <HOSO>
    <FILEHOSO>
      <LOAIHOSO>XML10</LOAIHOSO>
      <NOIDUNGFILE>
        <KHAM_THE_LUC>
          <CHIEU_CAO>168</CHIEU_CAO>
          <CAN_NANG>60</CAN_NANG>
        </KHAM_THE_LUC>
      </NOIDUNGFILE>
    </FILEHOSO>
    <FILEHOSO>
      <LOAIHOSO>XML7</LOAIHOSO>
      <NOIDUNGFILE>
        <KHAM_LAM_SANG>
          <KHONG_KINH_MAT_PHAI>10/10</KHONG_KINH_MAT_PHAI>
          <CKDT_KHAM_MAT>AAAA</CKDT_KHAM_MAT>
        </KHAM_LAM_SANG>
      </NOIDUNGFILE>
    </FILEHOSO>
    <FILEHOSO>
      <LOAIHOSO>XML11</LOAIHOSO>
      <NOIDUNGFILE>
        <KHAM_CAN_LAM_SANG>
          <DANH_SACH_CLS>
            <CHI_TIET_CLS>
              <MA_DICH_VU>03C3.1.89</MA_DICH_VU>
              <MA_CHI_SO>H02</MA_CHI_SO>
              <TEN_CHI_SO>Huyết sắc tố</TEN_CHI_SO>
            </CHI_TIET_CLS>
          </DANH_SACH_CLS>
        </KHAM_CAN_LAM_SANG>
      </NOIDUNGFILE>
    </FILEHOSO>
  </HOSO>
</KHAMSUCKHOE>
"""


class SyncMappingVersionTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin", email="ver-admin@nsync.test")
        self.doctor = _make_user("doctor", email="ver-doctor@nsync.test")

    def test_extract_skips_signature_images(self) -> None:
        from io import BytesIO

        fields = extract_mapping_fields(BytesIO(_SAMPLE_XML.encode("utf-8")))
        tags = {item["tag"] for item in fields}
        self.assertIn("CHIEU_CAO", tags)
        self.assertNotIn("CKDT_KHAM_MAT", tags)
        height = next(item for item in fields if item["tag"] == "CHIEU_CAO")
        self.assertEqual(height["label"], "Chiều cao")
        lab = next(item for item in fields if item["block"] == "xml11")
        self.assertEqual(lab["ma_chi_so"], "H02")
        self.assertEqual(lab["label"], "Huyết sắc tố")

    def test_extract_xml11_keeps_indicator_without_service_code(self) -> None:
        from io import BytesIO

        xml = """<?xml version="1.0" encoding="utf-8"?>
<KHAMSUCKHOE><HOSO><FILEHOSO><LOAIHOSO>XML11</LOAIHOSO><NOIDUNGFILE>
<KHAM_CAN_LAM_SANG><DANH_SACH_CLS>
  <CHI_TIET_CLS>
    <MA_DICH_VU></MA_DICH_VU>
    <MA_CHI_SO></MA_CHI_SO>
    <TEN_CHI_SO><![CDATA[Tổng phân tích tế bào máu]]></TEN_CHI_SO>
  </CHI_TIET_CLS>
  <CHI_TIET_CLS>
    <MA_DICH_VU>
    </MA_DICH_VU>
    <MA_CHI_SO>H17</MA_CHI_SO>
    <TEN_CHI_SO><![CDATA[Số lượng bạch cầu]]></TEN_CHI_SO>
  </CHI_TIET_CLS>
</DANH_SACH_CLS></KHAM_CAN_LAM_SANG>
</NOIDUNGFILE></FILEHOSO></HOSO></KHAMSUCKHOE>
"""
        fields = extract_mapping_fields(BytesIO(xml.encode("utf-8")))
        labs = [item for item in fields if item["block"] == "xml11"]
        self.assertEqual(len(labs), 1)
        self.assertEqual(labs[0]["ma_dich_vu"], "")
        self.assertEqual(labs[0]["ma_chi_so"], "H17")
        self.assertEqual(labs[0]["label"], "Số lượng bạch cầu")

    def test_upload_copies_matching_mappings_and_set_default(self) -> None:
        self.client.force_authenticate(self.admin)
        first = self.client.post(
            "/api/sync/mapping-versions/",
            {
                "name": "Lần 1",
                "file": SimpleUploadedFile("mau.xml", _SAMPLE_XML.encode("utf-8")),
            },
            format="multipart",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED, first.data)
        self.assertTrue(first.data["is_default"])
        self.assertGreater(first.data["field_count"], 0)

        department = Department.objects.create(name="Khám lâm sàng", code="ls_ver")
        SyncFieldMapping.objects.create(
            version_id=first.data["id"],
            block="xml10",
            xml_tag="CHIEU_CAO",
            department=department,
            field_key="chieu_cao",
        )
        second = self.client.post(
            "/api/sync/mapping-versions/",
            {
                "name": "Lần 2",
                "file": SimpleUploadedFile("mau.xml", _SAMPLE_XML.encode("utf-8")),
            },
            format="multipart",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED, second.data)
        self.assertFalse(second.data["is_default"])
        copied = SyncFieldMapping.objects.get(version_id=second.data["id"])
        self.assertEqual(copied.field_key, "chieu_cao")

        activated = self.client.post(
            f"/api/sync/mapping-versions/{second.data['id']}/set-default/"
        )
        self.assertEqual(activated.status_code, status.HTTP_200_OK)
        self.assertTrue(activated.data["is_default"])
        first_row = SyncMappingVersion.objects.get(pk=first.data["id"])
        self.assertFalse(first_row.is_default)

        self.client.force_authenticate(self.doctor)
        forbidden = self.client.post(
            "/api/sync/mapping-versions/",
            {"file": SimpleUploadedFile("mau.xml", _SAMPLE_XML.encode("utf-8"))},
            format="multipart",
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_xml_is_rejected(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/sync/mapping-versions/",
            {"file": SimpleUploadedFile("bad.xml", b"<not-xml")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UsbSignerDownloadTests(APITestCase):
    def test_doctor_can_download_signer(self) -> None:
        doctor = _make_user("doctor", email="usb-doctor@nsync.test")
        self.client.force_authenticate(doctor)
        response = self.client.get("/api/sync/usb-signer/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = b"".join(response.streaming_content)
        self.assertTrue(body.startswith(b"@echo off\r\n"))
        self.assertIn(b"###VIETTEL_CA_SIGNER###", body)
        self.assertIn(b"127.0.0.1:17611", body)
        self.assertIn("Ky_USB_ViettelCA.cmd", response["Content-Disposition"])

    def test_nurse_cannot_download_signer(self) -> None:
        nurse = _make_user("nurse", email="usb-nurse@nsync.test")
        self.client.force_authenticate(nurse)
        response = self.client.get("/api/sync/usb-signer/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
