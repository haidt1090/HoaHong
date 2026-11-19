from __future__ import annotations

from typing import Any

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)

    if response is None:
        return Response(
            {"detail": "An unexpected error occurred.", "code": "server_error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, ValidationError):
        # Preserve DRF's field-level validation errors so the frontend can
        # show per-field messages.  Just tag the response with a code.
        response.data = {**response.data, "code": "validation_error"}
        return response

    error_code = "error"
    if isinstance(response.data, dict):
        detail = response.data.get("detail", "Bad request.")
    else:
        detail = str(response.data)

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        error_code = "authentication_error"
    elif response.status_code == status.HTTP_403_FORBIDDEN:
        error_code = "permission_denied"
    elif response.status_code == status.HTTP_404_NOT_FOUND:
        error_code = "not_found"

    response.data = {"detail": detail, "code": error_code}
    return response
