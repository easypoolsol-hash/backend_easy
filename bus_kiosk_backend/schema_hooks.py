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
        '/health/',
        '/health/detailed/',
        '/metrics/',
    ]

    for path, path_regex, method, callback in endpoints:
        # Check if this endpoint should be excluded
        should_exclude = any(pattern in path for pattern in excluded_patterns)
        if should_exclude:
            continue
        filtered_endpoints.append((path, path_regex, method, callback))

    return filtered_endpoints
