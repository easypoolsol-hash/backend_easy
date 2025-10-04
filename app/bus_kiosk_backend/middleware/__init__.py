"""
Industrial-grade middleware for enhanced security, monitoring, and performance.
"""

from collections.abc import Callable
import time
import uuid

from django.http import HttpRequest, HttpResponse
from django.utils import timezone


class RequestLoggingMiddleware:
    """
    Middleware for comprehensive request/response logging.

    Logs all API requests with timing, user info, and response codes.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        # Add request_id as a dynamic attribute for logging
        request.request_id = request_id  # type: ignore[attr-defined]

        # Start timing
        start_time = time.time()

        # Log incoming request
        self._log_request(request)

        # Process request
        response = self.get_response(request)

        # Calculate duration
        duration = time.time() - start_time

        # Add response headers
        response["X-Request-ID"] = request_id
        response["X-Response-Time"] = f"{duration:.3f}s"

        # Log response
        self._log_response(request, response, duration)

        return response

    def _log_request(self, request: HttpRequest) -> None:
        """Log incoming request details."""
        import logging

        logger = logging.getLogger("bus_kiosk_backend.requests")

        log_data = {
            "request_id": getattr(request, "request_id", "unknown"),
            "method": request.method,
            "path": request.path,
            "query_params": dict(request.GET),
            "user_id": getattr(request.user, "id", None)
            if hasattr(request, "user")
            else None,
            "user_agent": request.META.get("HTTP_USER_AGENT"),
            "ip_address": self._get_client_ip(request),
            "timestamp": timezone.now().isoformat(),
        }

        logger.info("API Request", extra=log_data)

    def _log_response(
        self, request: HttpRequest, response: HttpResponse, duration: float
    ) -> None:
        """Log response details."""
        import logging

        logger = logging.getLogger("bus_kiosk_backend.responses")

        log_data = {
            "request_id": getattr(request, "request_id", "unknown"),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration": f"{duration:.3f}",
            "user_id": getattr(request.user, "id", None)
            if hasattr(request, "user")
            else None,
            "timestamp": timezone.now().isoformat(),
        }

        if response.status_code >= 400:
            logger.warning("API Response Error", extra=log_data)
        else:
            logger.info("API Response", extra=log_data)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Get the client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR", "")
        return ip


class SecurityHeadersMiddleware:
    """
    Middleware to add security headers to all responses.

    Implements OWASP security headers for enhanced protection.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        # Security headers
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=()"
        )

        # Content Security Policy (restrictive for API)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "media-src 'none'; "
            "object-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        return response
