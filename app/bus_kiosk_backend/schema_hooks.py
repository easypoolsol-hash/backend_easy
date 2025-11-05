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
