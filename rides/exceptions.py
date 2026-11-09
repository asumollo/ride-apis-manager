import logging
from typing import Any

from django.conf import settings
from django.db import IntegrityError, OperationalError
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    # DRF already turns its own errors into JSON: 400, 401, 403, 404, 405, 415
    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, ProtectedError):
        return Response(
            {"detail": "Other records still point to this one, so it can't be deleted."},
            status=status.HTTP_409_CONFLICT,
        )
    if isinstance(exc, IntegrityError):
        return Response(
            {"detail": "This change conflicts with existing data."},
            status=status.HTTP_409_CONFLICT,
        )

    logger.exception("Unhandled error in %s", context["view"].__class__.__name__)
    if settings.DEBUG:
        return None  # let Django show its debug page with the traceback

    if isinstance(exc, OperationalError):
        return Response(
            {"detail": "The database is unavailable right now. Try again shortly."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(
        {"detail": "Something went wrong on our side."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
