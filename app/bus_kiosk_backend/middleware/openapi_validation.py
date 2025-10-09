"""
Production OpenAPI Validation Middleware

Industry Standard: Uses openapi-core for enterprise-grade validation
Validates requests/responses against OpenAPI 3.0 specification
"""

import logging
import os
from typing import Any

from django.conf import settings
from django.http import JsonResponse
from openapi_core import Spec
from openapi_core.contrib.django import (
    DjangoOpenAPIRequest,
    DjangoOpenAPIResponse,
)
from openapi_core.validation.request.validators import APICallRequestValidator
from openapi_core.validation.response.validators import APICallResponseValidator
from prance import ResolvingParser  # type: ignore

logger = logging.getLogger(__name__)


class OpenAPIValidationMiddleware:
    """
    Django middleware for OpenAPI request/response validation in production.

    Uses openapi-core for enterprise-grade validation against OpenAPI 3.0
    specification.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._spec = None
        self._validation_disabled = False

        self.validate_requests = getattr(settings, "OPENAPI_VALIDATE_REQUESTS", True)
        self.validate_responses = getattr(settings, "OPENAPI_VALIDATE_RESPONSES", True)
        self.fail_on_validation_error = getattr(
            settings, "OPENAPI_FAIL_ON_ERROR", False
        )

    @property
    def spec(self):
        """Lazy load OpenAPI specification."""
        if self._spec is None:
            # Load schema directly using prance
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            schema_path = os.path.join(base_dir, "openapi-schema.yaml")

            try:
                parser = ResolvingParser(schema_path)
                schema_dict = parser.specification
                self._spec = Spec.from_dict(schema_dict)
            except Exception as e:
                logger.error(f"Failed to load OpenAPI schema: {e}")
                logger.warning(
                    "OpenAPI validation will be disabled due to schema loading failure"
                )
                # Set a flag to disable validation instead of crashing
                self._validation_disabled = True
                self._spec = None  # Keep as None to indicate failure
        return self._spec

    def __call__(self, request):
        # Skip validation if disabled due to schema loading failure
        if self._validation_disabled:
            return self.get_response(request)

        # Validate request if enabled
        if self.validate_requests and self._should_validate_request(request):
            validation_result = self._validate_request(request)
            if not validation_result["valid"]:
                if self.fail_on_validation_error:
                    return self._handle_validation_error(
                        request, validation_result, "request"
                    )
                logger.warning(
                    "OpenAPI Request Validation Failed: %s %s",
                    request.path,
                    validation_result["errors"],
                )

        # Get response
        response = self.get_response(request)

        # Validate response if enabled
        if self.validate_responses and self._should_validate_response(response):
            validation_result = self._validate_response(request, response)
            if not validation_result["valid"]:
                if self.fail_on_validation_error:
                    return self._handle_validation_error(
                        request, validation_result, "response"
                    )
                logger.warning(
                    "OpenAPI Response Validation Failed: %s %s",
                    request.path,
                    validation_result["errors"],
                )

        return response

    def _should_validate_request(self, request) -> bool:
        """Determine if request should be validated."""
        # Skip validation for:
        # - Non-API endpoints
        # - Health checks
        # - Admin endpoints
        skip_paths = ["/health/", "/admin/", "/static/", "/media/"]
        return request.path.startswith("/api/") and not any(
            request.path.startswith(path) for path in skip_paths
        )

    def _should_validate_response(self, response) -> bool:
        """Determine if response should be validated."""
        # Only validate JSON responses
        content_type = response.get("Content-Type", "")
        return hasattr(response, "data") and content_type.startswith("application/json")

    def _validate_request(self, request) -> dict[str, Any]:
        """Validate incoming request against OpenAPI schema."""
        try:
            openapi_request = DjangoOpenAPIRequest(request)
            validator = APICallRequestValidator(self.spec)
            # Validate request - raises exception on failure
            validator.validate(openapi_request)
            return {"valid": True, "errors": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}

    def _validate_response(self, request, response) -> dict[str, Any]:
        """Validate outgoing response against OpenAPI schema."""
        try:
            openapi_request = DjangoOpenAPIRequest(request)
            openapi_response = DjangoOpenAPIResponse(response)
            validator = APICallResponseValidator(self.spec)
            # Validate response - raises exception on failure
            validator.validate(openapi_request, openapi_response)  # type: ignore
            return {"valid": True, "errors": []}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}

    def _handle_validation_error(self, request, validation_result, validation_type):
        """Handle validation errors based on configuration."""
        error_msg = f"OpenAPI {validation_type.title()} Validation Failed"
        logger.error(
            "%s: %s - %s", error_msg, request.path, validation_result["errors"]
        )

        return JsonResponse(
            {
                "error": error_msg,
                "details": validation_result["errors"],
                "path": request.path,
                "method": request.method,
            },
            status=400,
        )
