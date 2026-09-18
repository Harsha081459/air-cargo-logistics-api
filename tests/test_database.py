import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import mysql.connector
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="requires an isolated MySQL demo database and running API",
)


@pytest.fixture
def db():
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), user=os.getenv("DB_USER", "root"),
        password=os.environ["DB_PASSWORD"], database="air_cargo", autocommit=True,
    )
    yield conn
    conn.close()


@pytest.fixture
def client():
    with httpx.Client(base_url=os.getenv("CARGO_API_URL", "http://127.0.0.1:8000"), timeout=15) as client:
        response = client.post("/auth/login", json={"username": "agent", "password": "agent123"})
        response.raise_for_status()
        client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        yield client


@pytest.fixture
def flight(db):
    flight_id = "TEST-" + uuid4().hex[:12]
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO flight VALUES (%s, 'BLR', 'DEL', CURDATE(), 10)", (flight_id,)
    )
    cursor.close()
    return flight_id


def booking(flight, **changes):
    return {
        "tracking_number": "TEST-" + uuid4().hex[:12], "weight": 6,
        "cargo_type": "General", "total_cost": 100,
        "current_status": "Booked", "current_location": "BLR",
        "customer_id": "CUST001", "flight_id": flight, **changes,
    }


def scalar(db, sql, args):
    cursor = db.cursor()
    cursor.execute(sql, args)
    value = cursor.fetchone()[0]
    cursor.close()
    return value


def test_booking_readback_history_and_duplicate_rollback(db, client, flight):
    body = booking(flight, weight=3)
    assert client.post("/cargo", json=body).status_code == 201
    response = client.get(f"/shipments/{body['tracking_number']}")
    assert response.status_code == 200
    assert response.json()["data"]["CustomerName"] == "Acme Corp"
    assert scalar(db, "SELECT COUNT(*) FROM trackinghistory WHERE TrackingNumber=%s", (body["tracking_number"],)) == 1
    assert client.post("/cargo", json=body).status_code == 409
    assert scalar(db, "SELECT AvailableCapacity FROM flight WHERE FlightID=%s", (flight,)) == 7


def test_foreign_key_failure_restores_capacity_and_leaves_no_cargo(db, client, flight):
    body = booking(flight, customer_id="MISSING-CUSTOMER")
    assert client.post("/cargo", json=body).status_code == 400
    assert scalar(db, "SELECT AvailableCapacity FROM flight WHERE FlightID=%s", (flight,)) == 10
    assert scalar(db, "SELECT COUNT(*) FROM cargo WHERE TrackingNumber=%s", (body["tracking_number"],)) == 0


def test_concurrent_bookings_cannot_overbook(db, client, flight):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda body: client.post("/cargo", json=body), [booking(flight), booking(flight)]))
    assert sorted(response.status_code for response in responses) == [201, 409]
    assert scalar(db, "SELECT AvailableCapacity FROM flight WHERE FlightID=%s", (flight,)) == 4
    assert scalar(db, "SELECT COUNT(*) FROM booking WHERE FlightID=%s", (flight,)) == 1
