"""National sync URL routing — Phase 8, Sprint 16."""

from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from nationalsync.views import (
    FacilitySignatureImageView,
    FacilitySignatureView,
    SyncConfigView,
    SyncFieldMappingViewSet,
    SyncJobViewSet,
    SyncMappingVersionViewSet,
    SyncSigningXmlView,
    SyncTriggerView,
    SyncValidateView,
    UsbSignerDownloadView,
)

app_name = "nationalsync"

router = DefaultRouter()
router.register("jobs", SyncJobViewSet, basename="sync-job")
router.register(
    "field-mappings", SyncFieldMappingViewSet, basename="sync-field-mapping"
)
router.register(
    "mapping-versions", SyncMappingVersionViewSet, basename="sync-mapping-version"
)

urlpatterns = [
    *router.urls,
    path("config/", SyncConfigView.as_view(), name="sync-config"),
    path("validate/", SyncValidateView.as_view(), name="sync-validate"),
    path("signing-xml/", SyncSigningXmlView.as_view(), name="sync-signing-xml"),
    path("trigger/", SyncTriggerView.as_view(), name="sync-trigger"),
    path(
        "facility-signature/",
        FacilitySignatureView.as_view(),
        name="facility-signature",
    ),
    path(
        "facility-signature/image/",
        FacilitySignatureImageView.as_view(),
        name="facility-signature-image",
    ),
    path(
        "usb-signer/",
        UsbSignerDownloadView.as_view(),
        name="usb-signer-download",
    ),
]
