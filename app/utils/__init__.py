"""
Utilities package for the bus kiosk backend.

Contains:
- timezone_utils: Industry-standard timezone handling (UTC storage, IST display)
- serializer_mixins: DRF serializer mixins for common patterns
- admin_helpers: Django admin utilities
"""

__all__ = [
    "admin_helpers",
    "serializer_mixins",
    "timezone_utils",
]
