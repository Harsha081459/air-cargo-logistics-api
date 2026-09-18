# Air-Travel Cargo Services Database Engine 🚀

![CI](https://github.com/Harsha081459/air-cargo-logistics-api/actions/workflows/ci.yml/badge.svg)

A local-demo logistics REST API backed by a five-table MySQL schema. Agents book cargo onto flights and retrieve shipment details; viewers have read-only access. Booking reserves capacity and inserts cargo, booking and initial tracking history in one InnoDB transaction. This is a coursework prototype, not a production-certified service.

*Project period: Built Apr–May 2025 (DBMS course project); published to GitHub Sep 2026.*

## 🏗️ Architecture

- **Backend Framework**: FastAPI (Python)
- **Database**: MySQL 8.0 (Relational Database)
- **Deployment**: Docker & Docker Compose
- **Security**: Signed HS256 JWTs with role-based access control (admin / agent / viewer)

### Schema

Five tables in the `air_cargo` database (`schema.sql`):

| Table | Purpose | Key relationships |
|-------|---------|-------------------|
| `customer` | Shipper accounts (contact details, password hash) | referenced by `booking.CustomerID` |
| `cargo` | Physical cargo items (`TrackingNumber` PK) | referenced by `booking` and `trackinghistory` |
| `flight` | Flight legs between hubs with capacity | referenced by `booking.FlightID` |
| `booking` | Links one cargo item + customer + flight | FKs → `cargo`, `customer`, `flight` (all `ON DELETE CASCADE`) |
| `trackinghistory` | Status/location audit trail per cargo item | FK → `cargo.TrackingNumber` (`ON DELETE CASCADE`) |

## ✨ Key Features

1. **Atomic bookings**: A conditional capacity update prevents oversubscription; capacity and all three inserts commit together or roll back. Invalid weights, negative prices and oversized fields are rejected before database access.
2. **Referential Integrity**: Implements strict `ON DELETE CASCADE` foreign key constraints across a normalized 5-table schema.
3. **Complex JOINs**: Real-time aggregation of cargo status, customer data, and flight manifests via normalized query mapping.
4. **REST API**: Exposes core functionality via `/cargo`, `/shipments/{id}` and `/flights` endpoints.
5. **JWT + RBAC Security**: Signed, expiring bearer tokens issued by `/auth/login`, with per-endpoint role enforcement and PBKDF2-hashed passwords — covered by a 10-case test suite.

## 🚀 Getting Started (Docker)

The entire application is containerized. You can spin up both the FastAPI web server and the MySQL database with a single command:

```bash
git clone https://github.com/Harsha081459/air-cargo-logistics-api.git
cd air-cargo-logistics-api
docker compose up --build -d --wait
```

Once running:
- **API Docs (Swagger UI)**: http://localhost:8000/docs
- **API Host**: http://localhost:8000

Or run without Docker:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
uvicorn app:app --reload      # needs a reachable MySQL instance (see schema.sql / seed.sql)
```

## 🔐 Authentication & Authorization

The API issues **signed HS256 JSON Web Tokens** and enforces **role-based access control** on
every data endpoint.

**1. Obtain a token**

```bash
curl -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}'
```

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 3600, "role": "admin" }
```

**2. Call a protected endpoint**

```bash
curl http://localhost:8000/flights -H "Authorization: Bearer <access_token>"
```

In Swagger UI, click **Authorize** and paste the `access_token`.

**3. Book and track a shipment**

Use `POST /cargo` in Swagger with the following body. `CUST001` and `FL-101` are installed by `seed.sql`:

```json
{"tracking_number":"DEMO-0001","weight":12.5,"cargo_type":"General","total_cost":100,"current_status":"Booked","current_location":"JFK","customer_id":"CUST001","flight_id":"FL-101"}
```

Expect HTTP 201 with a booking ID, then call `GET /shipments/DEMO-0001` to see the customer/flight join. `/flights` now shows 12.5 less available capacity. Repeating the same request returns 409 without consuming more capacity; an unknown customer returns 400 and rolls back. Use a new tracking number for another booking. Flight weights/capacities are in the same demo units (kg).

The Compose ports bind only to localhost. Stop the demo with `docker compose stop`. The initialization scripts run only against a new database volume. **Do not execute `schema.sql` against an existing database: it drops the project's tables.**

### Role matrix

| Role | Read shipments & flights | Create cargo |
|------|:------------------------:|:------------:|
| `admin`  | ✅ | ✅ |
| `agent`  | ✅ | ✅ |
| `viewer` | ✅ | ❌ 403 |

### Security notes

- Passwords are salted per user and hashed with **PBKDF2-HMAC-SHA256** (100,000 iterations);
  no plaintext credential survives startup.
- Login compares digests with `hmac.compare_digest`, and hashes even for unknown usernames so
  the response time does not leak whether an account exists.
- Tokens carry `sub`, `role`, `iat` and `exp` claims and expire after `JWT_TTL_MINUTES`
  (default 60). Expired or tampered tokens are rejected with `401`.

### Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `JWT_SECRET` | random per process | Set a stable secret for shared workers; otherwise restart invalidates all tokens |
| `JWT_TTL_MINUTES` | `60` | Token lifetime |
| `ADMIN_PASSWORD` / `AGENT_PASSWORD` / `VIEWER_PASSWORD` | `admin123` / `agent123` / `viewer123` | Demo credentials |

> The demo credential store lives in `app.py`. A production deployment would back it with a
> `users` table; the JWT issuing, verification and RBAC layers would be unchanged.

## 🧪 Tests

`tests/test_auth.py` covers the auth and RBAC paths (signature validation, expiry, tampering,
role enforcement, password storage) and needs **no running database** — it only imports
`app.py` (the `mysql.connector` package must be installed, but no server connection is opened):

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

The local suite includes auth, validation, transaction boundaries and booking-ID regressions. The separate `database-integration` CI job builds Docker Compose on a fresh runner and tests real MySQL booking/readback, rollback on duplicate/invalid references, and two simultaneous bookings competing for capacity. `tests/test_database.py` is skipped unless `RUN_DB_INTEGRATION=1`; run it only against a disposable demo database (it inserts test records).

Database connection settings are `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Compose also forwards `JWT_SECRET`, `JWT_TTL_MINUTES` and the three role passwords. Set those in a local, uncommitted `.env` for Compose; shell environment variables are used for direct Uvicorn runs.

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| API framework | FastAPI 0.110 + Uvicorn |
| Database | MySQL 8.0 via mysql-connector-python |
| Auth | PyJWT (HS256) + PBKDF2-HMAC-SHA256 |
| Data validation | Pydantic 2 |
| Deployment | Docker / docker-compose |
| Tests | pytest + FastAPI TestClient |

## ⚠️ Limitations

- **Demo credential store**: users are seeded in `app.py` (`USERS` dict, app.py:56)
  from `*_PASSWORD` env vars with defaults `admin123`/`agent123`/`viewer123` — not
  a `users` table.
- **Demo security only**: change the role passwords before any non-local use. Without an explicit `JWT_SECRET`, tokens are invalidated on process restart. There is no login throttling, TLS termination or persistent user administration.
- **No pagination**: `GET /flights` returns `cursor.fetchall()` (`app.py:229`) —
  fine for demo data, unbounded for large tables.
- **No migrations tool**: schema evolution is manual via `schema.sql` / `seed.sql`.
- **Small API surface**: `/cargo` (POST), `/shipments/{id}`, `/flights`, `/auth/*`
  only — no update/delete endpoints.

## 💻 Legacy CLI Tool
The original terminal-based Python tool is preserved in `main.py` for legacy manual testing and direct database administration.

## 📝 License

MIT — see [LICENSE](LICENSE).
