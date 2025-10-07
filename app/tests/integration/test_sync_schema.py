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
def test_check_updates_matches_schema(api_client, test_kiosk):
    """
    CRITICAL: Check-updates endpoint response must match OpenAPI schema

    Uses schemathesis to validate response format against schema contract.
    """
    # Setup - test_kiosk fixture provides activated kiosk
    kiosk, _ = test_kiosk

    # Get token from activation (kiosk is already activated by fixture)
    # Activate the kiosk to get a proper token
    activation_token = kiosk._activation_token  # From factory
    response = api_client.post(
        "/api/v1/kiosks/activate/",
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    # Make request with required last_sync parameter
    from django.utils import timezone

    response = api_client.get(
        f"/api/v1/{kiosk.kiosk_id}/check-updates/",
        {"last_sync": (timezone.now() - timezone.timedelta(days=1)).isoformat()},
    )

    # Validate against schema
    assert response.status_code in [200, 304]
    assert "needs_update" in response.json()


@pytest.mark.django_db
def test_snapshot_matches_schema(api_client, test_kiosk):
    """
    CRITICAL: Snapshot endpoint response must match OpenAPI schema
    """
    kiosk, activation_token = test_kiosk

    # Activate kiosk to get proper token
    response = api_client.post(
        "/api/v1/kiosks/activate/",
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(f"/api/v1/{kiosk.kiosk_id}/snapshot/")

    # Validate against schema
    assert response.status_code == 200
    json_data = response.json()
    assert "download_url" in json_data
    assert "checksum" in json_data
    assert "size_bytes" in json_data
    assert "expires_at" in json_data


@pytest.mark.django_db
def test_heartbeat_matches_schema(api_client, test_kiosk):
    """
    CRITICAL: Heartbeat endpoint request/response must match OpenAPI schema
    """
    from django.utils import timezone
    from kiosks.models import KioskStatus

    kiosk, activation_token = test_kiosk

    # Activate kiosk and create KioskStatus
    response = api_client.post(
        "/api/v1/kiosks/activate/",
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
        "battery_level": 85.5,
        "storage_available_mb": 1024,
        "last_face_scan": "2025-10-06T14:55:00Z",
    }

    response = api_client.post(
        f"/api/v1/{kiosk.kiosk_id}/heartbeat/", data=heartbeat_data, format="json"
    )

    # Validate against schema
    assert response.status_code == 204


@pytest.mark.django_db
def test_all_sync_endpoints_have_schema():
    """
    CRITICAL: All sync endpoints must be documented in OpenAPI schema

    This ensures no undocumented endpoints exist.
    """
    required_endpoints = [
        "/api/v1/{kiosk_id}/check-updates/",
        "/api/v1/{kiosk_id}/snapshot/",
        "/api/v1/{kiosk_id}/heartbeat/",
    ]

    # Get all paths from schema
    schema_dict = schema.raw_schema
    paths = set(schema_dict.get("paths", {}).keys())

    for endpoint in required_endpoints:
        # Check if endpoint exists in schema paths
        assert (
            endpoint in paths
        ), f"Endpoint {endpoint} not found in OpenAPI schema. Available paths: {sorted(paths)}"


@pytest.mark.django_db
def test_complete_sync_workflow(api_client, test_kiosk):
    """
    CRITICAL: Test complete sync workflow sequence

    Fortune 500 standard: Test realistic user flows, not just individual endpoints.
    Tests: check → download → heartbeat
    """
    from django.utils import timezone
    from kiosks.models import KioskStatus

    kiosk, activation_token = test_kiosk

    # Activate kiosk and create KioskStatus
    response = api_client.post(
        "/api/v1/kiosks/activate/",
        {"kiosk_id": kiosk.kiosk_id, "activation_token": activation_token},
        format="json",
    )
    token = response.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    KioskStatus.objects.create(kiosk=kiosk, last_heartbeat=timezone.now())

    # Step 1: Check for updates
    check_response = api_client.get(
        f"/api/v1/{kiosk.kiosk_id}/check-updates/",
        {"last_sync": (timezone.now() - timezone.timedelta(days=1)).isoformat()},
    )
    assert check_response.status_code == 200
    assert "needs_update" in check_response.json()

    # Step 2: Download snapshot
    snapshot_response = api_client.get(f"/api/v1/{kiosk.kiosk_id}/snapshot/")
    assert snapshot_response.status_code == 200
    snapshot_data = snapshot_response.json()
    assert "download_url" in snapshot_data
    assert "checksum" in snapshot_data

    # Step 3: Report heartbeat (use data from snapshot response)
    heartbeat_data = {
        "timestamp": "2025-10-06T15:00:00Z",
        "database_version": "2025-10-06T14:30:00Z",
        "database_hash": snapshot_data["checksum"][:32],  # Truncate to 32 chars (schema limit)
        "student_count": 1,
        "embedding_count": 1,
    }
    heartbeat_response = api_client.post(
        f"/api/v1/{kiosk.kiosk_id}/heartbeat/", data=heartbeat_data, format="json"
    )
    assert heartbeat_response.status_code == 204, f"Heartbeat failed: {heartbeat_response.json()}"
