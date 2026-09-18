from unittest.mock import MagicMock

import jwt
import mysql.connector
import pytest
from fastapi.testclient import TestClient

import app as api


@pytest.fixture
def client():
    with TestClient(api.app) as client:
        client.headers["Authorization"] = f"Bearer {api.create_access_token('agent', 'agent')}"
        yield client


@pytest.fixture
def database(monkeypatch):
    connection = MagicMock()
    connection.cursor.return_value.rowcount = 1
    monkeypatch.setattr(api, "get_db_connection", lambda: connection)
    return connection


def payload(**changes):
    return {
        "tracking_number": "DEMO-1234", "weight": 12.5,
        "cargo_type": "General", "total_cost": 100,
        "current_status": "Booked", "current_location": "BLR",
        "customer_id": "CUST001", "flight_id": "FL-101", **changes,
    }


@pytest.mark.parametrize("changes", [
    {"weight": -1}, {"weight": 0}, {"total_cost": -1},
    {"tracking_number": "x" * 21}, {"flight_id": " "},
    {"current_location": "x" * 101},
])
def test_invalid_cargo_never_opens_database(client, monkeypatch, changes):
    connect = MagicMock(side_effect=AssertionError("validation must precede database access"))
    monkeypatch.setattr(api, "get_db_connection", connect)
    assert client.post("/cargo", json=payload(**changes)).status_code == 422
    connect.assert_not_called()


def test_success_reserves_capacity_and_commits_all_rows(client, database):
    response = client.post("/cargo", json=payload())
    assert response.status_code == 201
    calls = database.cursor.return_value.execute.call_args_list
    assert "UPDATE flight" in calls[0].args[0]
    assert calls[0].args[1] == (12.5, "FL-101", 12.5)
    assert len(calls) == 4
    database.commit.assert_called_once()
    database.rollback.assert_not_called()
    database.close.assert_called_once()


def test_insufficient_capacity_rolls_back_without_inserts(client, database):
    database.cursor.return_value.rowcount = 0
    assert client.post("/cargo", json=payload()).status_code == 409
    assert database.cursor.return_value.execute.call_count == 1
    database.rollback.assert_called_once()
    database.commit.assert_not_called()


def test_foreign_key_error_rolls_back_capacity_and_cargo(client, database):
    database.cursor.return_value.execute.side_effect = [
        None, None, mysql.connector.IntegrityError("private database details", errno=1452)
    ]
    response = client.post("/cargo", json=payload())
    assert response.status_code == 400
    assert "private database details" not in response.text
    database.rollback.assert_called_once()
    database.commit.assert_not_called()
    database.cursor.return_value.close.assert_called_once()


def test_booking_ids_do_not_depend_on_tracking_suffix_or_clock(client, database):
    ids = {client.post("/cargo", json=payload()).json()["booking_id"] for _ in range(25)}
    assert len(ids) == 25
    assert all(len(value) <= 20 for value in ids)


def test_signed_token_without_expiry_is_rejected(client):
    token = jwt.encode({"sub": "agent", "role": "agent"}, api.JWT_SECRET, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
