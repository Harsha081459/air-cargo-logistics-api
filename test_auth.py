"""
Auth + RBAC test suite for the Air-Travel Cargo Services API.

These tests exercise the JWT signing, verification and role-enforcement paths only,
so they run without a live MySQL instance.

    pytest test_auth.py -v          # with pytest
    python test_auth.py             # standalone
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

import app as api

client = TestClient(api.app)


def _token(username: str, password: str) -> str:
    response = client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_health_is_public():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_returns_signed_token():
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"

    claims = jwt.decode(
        body["access_token"], api.JWT_SECRET, algorithms=[api.JWT_ALGORITHM]
    )
    assert claims["sub"] == "admin"
    assert claims["role"] == "admin"
    assert claims["exp"] > claims["iat"]


def test_login_rejects_wrong_password():
    response = client.post(
        "/auth/login", json={"username": "admin", "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_login_rejects_unknown_user():
    response = client.post(
        "/auth/login", json={"username": "ghost", "password": "admin123"}
    )
    assert response.status_code == 401


def test_protected_route_requires_a_token():
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)


def test_protected_route_accepts_valid_token():
    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {_token('viewer', 'viewer123')}"}
    )
    assert response.status_code == 200
    assert response.json() == {"username": "viewer", "role": "viewer"}


def test_tampered_signature_is_rejected():
    forged = jwt.encode(
        {
            "sub": "admin",
            "role": "admin",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "the-wrong-secret",
        algorithm=api.JWT_ALGORITHM,
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_expired_token_is_rejected():
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    expired = jwt.encode(
        {"sub": "admin", "role": "admin", "iat": past, "exp": past + timedelta(minutes=1)},
        api.JWT_SECRET,
        algorithm=api.JWT_ALGORITHM,
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_viewer_cannot_create_cargo():
    """RBAC: the write endpoint must reject a read-only role before touching the DB."""
    payload = {
        "tracking_number": "TRK-0001",
        "weight": 12.5,
        "cargo_type": "general",
        "total_cost": 900.0,
        "current_status": "booked",
        "current_location": "BLR",
        "customer_id": "CUST-1",
        "flight_id": "FL-1",
    }
    response = client.post(
        "/cargo",
        json=payload,
        headers={"Authorization": f"Bearer {_token('viewer', 'viewer123')}"},
    )
    assert response.status_code == 403
    assert "not permitted" in response.json()["detail"]


def test_passwords_are_not_stored_in_plaintext():
    for username, record in api.USERS.items():
        assert "password" not in record
        assert len(record["password_hash"]) == 64  # sha256 hex digest
        assert record["salt"] != record["password_hash"]


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failed += 1
                print(f"FAIL  {name}: {exc}")
            else:
                passed += 1
                print(f"PASS  {name}")
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
