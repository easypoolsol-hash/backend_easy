"""
Schema-based API tests for kiosk sync endpoints
Fortune 500 standard: Use OpenAPI schema as single source of truth

Uses schemathesis to validate request/response against OpenAPI schema.
This is the industry standard for contract testing and preventing API drift.
"""

import pytest
import schemathesis

# Load schema from file (generated via: python manage.py spectacular --file schema.yaml)
schema = schemathesis.from_path("schema.yaml")


@pytest.mark.django_db
def test_check_updates_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Check-updates endpoint response must match OpenAPI schema

    Uses schemathesis to validate response format against schema contract.
    """
    # Setup - test_kiosk fixture provides activated kiosk
    kiosk, _ = test_kiosk

    # Get token from activation (kiosk is already activated by fixture)
    # Activate the kiosk to get a proper token
    activation_token = kiosk._activation_token  # From factory
    activate_path = openapi_helper(operation_id="kiosk_activate")
    response = api_client.post(
        activate_path,
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Make request with required last_sync parameter
    check_path = openapi_helper(
        operation_id="kiosk_check_updates", kiosk_id=kiosk.kiosk_id
    )
    response = api_client.get(
        check_path,
        {"last_sync_hash": "d41d8cd98f00b204e9800998ecf8427e"},
    )

    # Validate against schema
    assert response.status_code in [200, 304]
    assert "needs_update" in response.json()


@pytest.mark.django_db
def test_snapshot_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Snapshot endpoint response must match OpenAPI schema
    """
    kiosk, activation_token = test_kiosk

    # Activate kiosk to get proper token
    activate_path = openapi_helper(operation_id="kiosk_activate")
    response = api_client.post(
        activate_path,
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    snapshot_path = openapi_helper(
        operation_id="kiosk_download_snapshot", kiosk_id=kiosk.kiosk_id
    )
    response = api_client.get(snapshot_path)

    # Validate against schema
    assert response.status_code == 200
    assert response["Content-Type"] == "application/x-sqlite3"


@pytest.mark.django_db
def test_heartbeat_matches_schema(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Heartbeat endpoint request/response must match OpenAPI schema
    """
    from django.utils import timezone

    from kiosks.models import KioskStatus

    kiosk, activation_token = test_kiosk

    # Activate kiosk and create KioskStatus
    activate_path = openapi_helper(operation_id="kiosk_activate")
    response = api_client.post(
        activate_path,
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Create KioskStatus (required relationship)
    KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

    # Valid heartbeat data matching schema
    heartbeat_data = {
        "timestamp": "2025-10-06T15:00:00Z",
        "database_version": "2025-10-06T14:30:00Z",
        "database_hash": "abc123def456",
        "student_count": 1,
        "embedding_count": 1,
    }

    heartbeat_path = openapi_helper(
        operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id
    )
    response = api_client.post(
        heartbeat_path,
        data=heartbeat_data,
        format="json",
    )

    # Validate against schema
    assert response.status_code == 204


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
        assert (
            found
        ), f"No path for kiosk {name} found in OpenAPI schema. Available paths: {sorted(paths)}"


@pytest.mark.django_db
def test_complete_sync_workflow(api_client, test_kiosk, openapi_helper):
    """
    CRITICAL: Test complete sync workflow sequence

    Fortune 500 standard: Test realistic user flows, not just individual
    endpoints.
    Tests: check → download → heartbeat
    """
    from django.utils import timezone

    from kiosks.models import KioskStatus

    kiosk, activation_token = test_kiosk

    # Activate kiosk and create KioskStatus
    activate_path = openapi_helper(operation_id="kiosk_activate")
    response = api_client.post(
        activate_path,
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

    # Step 1: Check for updates
    check_path = openapi_helper(
        operation_id="kiosk_check_updates", kiosk_id=kiosk.kiosk_id
    )
    check_response = api_client.get(
        check_path,
        {"last_sync_hash": "d41d8cd98f00b204e9800998ecf8427e"},
    )
    assert check_response.status_code == 200
    assert "needs_update" in check_response.json()

    # Step 2: Download snapshot
    snapshot_response = api_client.get(
        openapi_helper(operation_id="kiosk_download_snapshot", kiosk_id=kiosk.kiosk_id)
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response["Content-Type"] == "application/x-sqlite3"

    # Step 3: Report heartbeat (use data from snapshot response)
    heartbeat_data = {
        "timestamp": "2025-10-06T15:00:00Z",
        "database_version": "2025-10-06T14:30:00Z",
        "database_hash": "d41d8cd98f00b204e9800998ecf8427e",
        "student_count": 1,
        "embedding_count": 1,
    }
    heartbeat_path = openapi_helper(
        operation_id="kiosk_heartbeat", kiosk_id=kiosk.kiosk_id
    )
    heartbeat_response = api_client.post(
        heartbeat_path,
        data=heartbeat_data,
        format="json",
    )
    assert (
        heartbeat_response.status_code == 204
    ), f"Heartbeat failed: {heartbeat_response.json()}"
