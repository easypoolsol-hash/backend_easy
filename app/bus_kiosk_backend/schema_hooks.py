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
    Postprocessing hook for drf-spectacular that ensures the kiosk
    activation operation is marked public (no security requirements).

    This is useful when a global SECURITY setting exists but a single
    operation (device activation) must be unauthenticated.
    """
    # 'result' is the schema dict returned by the generator
    paths = result.get("paths", {})
    activation_path = "/api/v1/kiosks/activate/"
    post = paths.get(activation_path)
    if post is not None:
        post_op = post.get("post")
        if post_op is not None:
            # Explicitly set empty security to override any global security
            post_op["security"] = []

    return result
