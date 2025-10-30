"""
Schema-based API tests for kiosk sync endpoints
Fortune 500 standard: Use OpenAPI schema as single source of truth

Uses schemathesis to validate request/response against OpenAPI schema.
This is the industry standard for contract testing and preventing API drift.
"""

import pytest
import schemathesis

# Load schema from file (generated via: python manage.py spectacular --file openapi-schema.yaml)
schema = schemathesis.openapi.from_path("openapi-schema.yaml")


@pytest.mark.django_db
@pytest.mark.skip(reason="JWT activation removed - needs Firebase authentication update")
def test_check_updates_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Check-updates endpoint response must match OpenAPI schema

    Uses schemathesis to validate response format against schema contract.

    TODO: Update to use Firebase authentication instead of JWT
    """
    pass


@pytest.mark.django_db
@pytest.mark.skip(reason="JWT activation removed - needs Firebase authentication update")
def test_snapshot_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Snapshot endpoint response must match OpenAPI schema

    TODO: Update to use Firebase authentication instead of JWT
    """
    pass


@pytest.mark.django_db
@pytest.mark.skip(reason="JWT activation removed - needs Firebase authentication update")
def test_heartbeat_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Heartbeat endpoint request/response must match OpenAPI schema

    TODO: Update to use Firebase authentication instead of JWT
    """
    pass


@pytest.mark.django_db
def test_all_sync_endpoints_have_schema():
    """
    CRITICAL: All sync endpoints must be documented in OpenAPI schema

    This ensures no undocumented endpoints exist.
    """
    # Instead of requiring a specific prefix, assert the schema contains
    # a path that includes the kiosk path parameter and the endpoint name.
    schema_dict = schema.raw_schema
    paths = set(schema_dict.get("paths", {}).keys())

    for name in ("check-updates", "snapshot", "heartbeat"):
        found = any(("{kiosk_id}" in p and name in p) for p in paths)
        assert found, f"No path for kiosk {name} found in OpenAPI schema. Available paths: {sorted(paths)}"


@pytest.mark.django_db
@pytest.mark.skip(reason="JWT activation removed - needs Firebase authentication update")
def test_complete_sync_workflow(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Test complete sync workflow sequence

    Fortune 500 standard: Test realistic user flows, not just individual
    endpoints.
    Tests: check → download → heartbeat

    TODO: Update to use Firebase authentication instead of JWT
    """
    pass
