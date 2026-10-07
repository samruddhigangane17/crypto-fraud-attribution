"""Tests for API health check endpoint."""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_api_health_endpoint():
    """Verify /health returns healthy status and service identity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "crypto-fraud-attribution-backend"
    assert "Member 2" in data["role_member_2"]
