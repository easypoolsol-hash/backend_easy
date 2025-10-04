"""
Custom exception handler for industrial-grade error responses.
"""

import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    PermissionDenied,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """
    Custom exception handler that provides detailed, structured error responses.

    Returns standardized error format for all API errors.
    """
    # Get the standard DRF error response
    response = exception_handler(exc, context)

    if response is not None:
        # Enhance the response with additional metadata
        response.data = {
            "error": {
                "code": get_error_code(exc, response.status_code),
                "message": get_error_message(exc, response.data),
                "details": response.data,
                "timestamp": None,  # Will be set by middleware
                "request_id": None,  # Will be set by middleware
            }
        }

        # Log the error for monitoring
        log_error(exc, context, response.status_code)

    return response


def get_error_code(exc: Exception, status_code: int) -> str:
    """Get a standardized error code for the exception."""
    error_codes = {
        status.HTTP_400_BAD_REQUEST: "VALIDATION_ERROR",
        status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_ERROR",
        status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
    }

    # Specific exception types
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    elif isinstance(exc, AuthenticationFailed):
        return "AUTHENTICATION_FAILED"
    elif isinstance(exc, PermissionDenied):
        return "PERMISSION_DENIED"
    elif isinstance(exc, Http404):
        return "NOT_FOUND"
    elif isinstance(exc, APIException):
        return f"API_ERROR_{exc.get_codes()}"
    else:
        return error_codes.get(status_code, "UNKNOWN_ERROR")


def get_error_message(exc: Exception, response_data: Any) -> str:
    """Extract a user-friendly error message."""
    if isinstance(exc, ValidationError):
        return "Validation failed. Please check your input data."
    elif isinstance(exc, AuthenticationFailed):
        return "Authentication credentials were not provided or are invalid."
    elif isinstance(exc, PermissionDenied):
        return "You do not have permission to perform this action."
    elif isinstance(exc, Http404):
        return "The requested resource was not found."
    elif hasattr(response_data, "get") and "detail" in response_data:
        return str(response_data["detail"])
    else:
        return "An unexpected error occurred. Please try again later."


def log_error(exc: Exception, context: dict[str, Any], status_code: int) -> None:
    """Log errors for monitoring and debugging."""
    view = context.get("view", {})
    request = context.get("request")

    log_data = {
        "exception_type": type(exc).__name__,
        "status_code": status_code,
        "view_name": getattr(view, "__name__", str(view)),
        "user_id": getattr(request.user, "id", None) if request else None,
        "method": request.method if request else None,
        "path": request.path if request else None,
        "user_agent": request.META.get("HTTP_USER_AGENT") if request else None,
        "ip_address": get_client_ip(request) if request else None,
    }

    if status_code >= 500:
        logger.error("Server Error", extra=log_data, exc_info=exc)
    elif status_code >= 400:
        logger.warning("Client Error", extra=log_data)
    else:
        logger.info("API Error", extra=log_data)


def get_client_ip(request) -> str:
    """Get the client IP address from the request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
