"""
Schema preprocessing hooks for drf-spectacular.
"""


def exclude_health_endpoints(endpoints):
    """
    Exclude health check and monitoring endpoints from OpenAPI schema.

    These endpoints are for operational monitoring and should not be
    part of the API documentation.
    """
    filtered_endpoints = []
    excluded_patterns = [
        "/health/",
        "/health/detailed/",
        "/metrics/",
    ]

    for path, path_regex, method, callback in endpoints:
        # Check if this endpoint should be excluded
        should_exclude = any(pattern in path for pattern in excluded_patterns)
        if should_exclude:
            continue
        filtered_endpoints.append((path, path_regex, method, callback))

    return filtered_endpoints


def mark_activation_public(result, generator=None, request=None, public=True):
    """
    Postprocessing hook for drf-spectacular that ensures public
    operations are marked as not requiring authentication.

    This is useful when a global SECURITY setting exists but specific
    operations must be unauthenticated.

    Note: Currently no activation endpoint exists - this is a placeholder
    for future implementation.
    """
    # 'result' is the schema dict returned by the generator
    # Placeholder - no current endpoints need this marking
    return result


def remove_nullable_from_required(result, generator=None, request=None, public=True):
    """
    Google Way: Remove nullable fields from the required array.

    This implements graceful degradation - fields can be null on error
    without failing the entire response. Nullable fields should not be
    marked as required since they can legitimately be null.

    Iterates through all schema components and removes any field marked
    as nullable: true from the required array.
    """
    if "components" not in result or "schemas" not in result["components"]:
        return result

    for schema_name, schema in result["components"]["schemas"].items():
        # Skip if no properties or no required array
        if "properties" not in schema or "required" not in schema:
            continue

        # Find nullable fields
        nullable_fields = []
        for field_name, field_schema in schema["properties"].items():
            if field_schema.get("nullable") is True:
                nullable_fields.append(field_name)

        # Remove nullable fields from required array
        if nullable_fields:
            schema["required"] = [
                field for field in schema["required"]
                if field not in nullable_fields
            ]

            # Remove required array if empty
            if not schema["required"]:
                del schema["required"]

    return result
