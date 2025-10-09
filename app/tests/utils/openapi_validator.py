"""
OpenAPI Schema Validator for API Testing

Industry Standard: Schema-driven API testing
Validates API respo    def validate_response(self, method: str, path: str, status_code: int,
                          response_data: Any, path_params: dict[str, str] | None = None) -> dict[str, Any]:es against OpenAPI specification
instead of hardcoded expectations.
"""

from datetime import datetime
import os
import re
from typing import Any
import uuid

from prance import ResolvingParser
from prance.util.url import ResolutionError


class OpenAPISchemaValidator:
    """
    Validates API responses against OpenAPI schema specification.

    Industry Standard: Contract testing with OpenAPI schemas
    """

    def __init__(self, schema_path: str | None = None):
        """
        Initialize validator with OpenAPI schema.

        Args:
            schema_path: Path to OpenAPI YAML file.
                        Defaults to openapi-schema.yaml in the app directory
        """
        if schema_path is None:
            # Default to the schema in the app directory
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            schema_path = os.path.join(base_dir, "openapi-schema.yaml")

        self.schema_path = schema_path
        self._schema: dict[str, Any] | None = None
        self._parser: ResolvingParser | None = None

    @property
    def schema(self) -> dict[str, Any]:
        """Lazy load and return the parsed OpenAPI schema."""
        if self._schema is None:
            self._load_schema()
        return self._schema

    @property
    def parser(self) -> ResolvingParser:
        """Lazy load and return the OpenAPI parser."""
        if self._parser is None:
            self._load_schema()
        return self._parser

    def _load_schema(self):
        """Load and parse the OpenAPI schema."""
        try:
            self._parser = ResolvingParser(self.schema_path)
            self._schema = self._parser.specification
        except ResolutionError as e:
            raise RuntimeError(f"Failed to parse OpenAPI schema: {e}") from e
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"OpenAPI schema file not found: {self.schema_path}"
            ) from exc

    def get_endpoint_schema(self, method: str, path: str) -> dict[str, Any] | None:
        """
        Get the schema for a specific endpoint.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /api/v1/kiosks/activate/)

        Returns:
            Schema for the endpoint response, or None if not found
        """
        method = method.lower()
        paths = self.schema.get("paths", {})

        # Find the path in the schema (handle path parameters)
        schema_path = None
        for schema_path_pattern in paths:
            if self._matches_path(schema_path_pattern, path):
                schema_path = schema_path_pattern
                break

        if not schema_path:
            return None

        path_schema = paths[schema_path]
        if method not in path_schema:
            return None

        return path_schema[method]

    def _matches_path(self, schema_path: str, actual_path: str) -> bool:
        """
        Check if an actual path matches a schema path pattern.

        Handles path parameters like {kiosk_id}.
        """
        # Convert schema path to regex pattern
        # Replace {param} with [^/]+
        pattern = re.sub(r"\{[^}]+\}", r"[^/]+", schema_path)
        pattern = f"^{pattern}$"

        return bool(re.match(pattern, actual_path))

    def validate_response(
        self,
        method: str,
        path: str,
        status_code: int,
        response_data: Any,
        path_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Validate a response against the OpenAPI schema.

        Args:
            method: HTTP method
            path: API path (may contain path parameters like {kiosk_id})
            status_code: HTTP status code
            response_data: Response data (dict, list, or primitive)
            path_params: Dictionary of path parameter values to substitute

        Returns:
            Dict with validation results
        """
        # Substitute path parameters if provided
        resolved_path = path
        if path_params:
            for param_name, param_value in path_params.items():
                resolved_path = resolved_path.replace(
                    f"{{{param_name}}}", str(param_value)
                )

        endpoint_schema = self.get_endpoint_schema(method, resolved_path)

        if not endpoint_schema:
            return {
                "valid": False,
                "errors": [f"No schema found for {method.upper()} " f"{resolved_path}"],
                "endpoint_found": False,
            }

        # Check if status code is defined
        responses = endpoint_schema.get("responses", {})
        status_str = str(status_code)

        if status_str not in responses:
            return {
                "valid": False,
                "errors": [
                    f"Status code {status_code} not defined "
                    f"in schema for {method.upper()} {resolved_path}"
                ],
                "endpoint_found": True,
            }

        response_schema = responses[status_str]
        content = response_schema.get("content", {})

        # For responses with no content (like 204),
        # validate that response_data is None/empty
        if not content:
            if response_data is None or response_data == "":
                return {"valid": True, "errors": [], "endpoint_found": True}
            else:
                return {
                    "valid": False,
                    "errors": [
                        f"Expected no content for {status_code} "
                        "response, but got data"
                    ],
                    "endpoint_found": True,
                }

        # Find JSON content schema
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        if not schema:
            # No schema defined for this response
            return {
                "valid": True,  # Consider it valid if no schema is defined
                "errors": [],
                "endpoint_found": True,
            }

        # Validate against schema
        return self._validate_against_schema(response_data, schema)

    def _validate_against_schema(
        self, data: Any, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate data against a JSON schema.

        This is a simplified validator. For production use,
        consider using jsonschema library.
        """
        errors = []
        processed_data = self._preprocess_data(data)
        schema_type = schema.get("type")

        if schema_type == "object":
            if not isinstance(processed_data, dict):
                errors.append(
                    f"Expected object, got " f"{type(processed_data).__name__}"
                )
                return {"valid": False, "errors": errors, "endpoint_found": True}

            # Check required properties
            required = schema.get("required", [])
            for prop in required:
                if prop not in processed_data:
                    errors.append(f"Missing required property: {prop}")

            # Validate properties
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in processed_data:
                    prop_result = self._validate_against_schema(
                        processed_data[prop_name], prop_schema
                    )
                    if not prop_result["valid"]:
                        errors.extend(
                            [f"{prop_name}: {err}" for err in prop_result["errors"]]
                        )

        elif schema_type == "array":
            if not isinstance(processed_data, list):
                errors.append(
                    f"Expected array, got " f"{type(processed_data).__name__}"
                )
                return {"valid": False, "errors": errors, "endpoint_found": True}

            # Validate items if schema provided
            items_schema = schema.get("items", {})
            if items_schema:
                for i, item in enumerate(processed_data):
                    item_result = self._validate_against_schema(item, items_schema)
                    if not item_result["valid"]:
                        errors.extend(
                            [f"[{i}]: {err}" for err in item_result["errors"]]
                        )

        elif schema_type == "string":
            if not isinstance(processed_data, str):
                errors.append(
                    f"Expected string, got " f"{type(processed_data).__name__}"
                )
                return {"valid": False, "errors": errors, "endpoint_found": True}

            # Check format constraints
            format_type = schema.get("format")
            if format_type == "uuid":
                try:
                    uuid.UUID(processed_data)
                except ValueError:
                    errors.append(f"Invalid UUID format: {processed_data}")
            elif format_type == "date-time":
                try:
                    datetime.fromisoformat(processed_data.replace("Z", "+00:00"))
                except ValueError:
                    errors.append(f"Invalid date-time format: " f"{processed_data}")

        elif schema_type == "integer":
            if not isinstance(processed_data, int):
                errors.append(
                    f"Expected integer, got " f"{type(processed_data).__name__}"
                )

        elif schema_type == "number":
            if not isinstance(processed_data, int | float):
                errors.append(
                    f"Expected number, got " f"{type(processed_data).__name__}"
                )

        elif schema_type == "boolean":
            if not isinstance(processed_data, bool):
                errors.append(
                    f"Expected boolean, got " f"{type(processed_data).__name__}"
                )

        return {"valid": len(errors) == 0, "errors": errors, "endpoint_found": True}

    def _preprocess_data(self, data: Any) -> Any:
        """
        Preprocess data to handle special types like UUID objects.

        Converts UUID objects to strings for schema validation.
        """
        if isinstance(data, uuid.UUID):
            return str(data)

        if isinstance(data, dict):
            return {key: self._preprocess_data(value) for key, value in data.items()}

        if isinstance(data, list):
            return [self._preprocess_data(item) for item in data]

        return data

    def assert_response_valid(
        self,
        method: str,
        path: str,
        status_code: int,
        response_data: Any,
        message: str = "",
    ):
        """
        Assert that a response is valid according to the OpenAPI schema.

        Raises AssertionError if validation fails.
        """
        result = self.validate_response(method, path, status_code, response_data)

        if not result["valid"]:
            error_parts = [
                f"OpenAPI Schema Validation Failed for "
                f"{method.upper()} {path} ({status_code}):"
            ]

            error_parts.extend(f"  - {err}" for err in result["errors"])

            if message:
                error_parts.insert(0, message)

            raise AssertionError("\n".join(error_parts))


# Global validator instance for tests
openapi_validator = OpenAPISchemaValidator()
