# Air-Travel Cargo Services Database Engine 🚀

![CI](https://github.com/Harsha081459/air-cargo-logistics-api/actions/workflows/ci.yml/badge.svg)

A robust, production-ready logistics database engine and REST API serving a normalized MySQL schema. This system tracks complex supply chain networks with strict ACID transaction management and JWT-based role-based access control.

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

1. **ACID-Compliant Transactions**: Handles multi-table inserts (Cargo, Booking, Tracking History) with `conn.commit()` and `conn.rollback()` to ensure zero data corruption during logistics updates.
2. **Referential Integrity**: Implements strict `ON DELETE CASCADE` foreign key constraints across a normalized 5-table schema.
3. **Complex JOINs**: Real-time aggregation of cargo status, customer data, and flight manifests via normalized query mapping.
4. **REST API**: Exposes core functionality via `/cargo`, `/shipments/{id}` and `/flights` endpoints.
5. **JWT + RBAC Security**: Signed, expiring bearer tokens issued by `/auth/login`, with per-endpoint role enforcement and PBKDF2-hashed passwords — covered by a 10-case test suite.

## 🚀 Getting Started (Docker)

The entire application is containerized. You can spin up both the FastAPI web server and the MySQL database with a single command:

```bash
git clone https://github.com/Harsha081459/air-cargo-logistics-api.git
cd air-cargo-logistics-api
docker-compose up --build -d
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
| `JWT_SECRET` | dev placeholder | HMAC signing key — **must** be set in production |
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
pytest tests/ -v      # or: python tests/test_auth.py
```

All 10 tests pass.

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
- **`JWT_SECRET` ships a dev default** (`app.py:34`); it must be set in production.
- **No pagination**: `GET /flights` returns `cursor.fetchall()` (`app.py:229`) —
  fine for demo data, unbounded for large tables.
- **No migrations tool**: schema evolution is manual via `schema.sql` / `seed.sql`.
- **Small API surface**: `/cargo` (POST), `/shipments/{id}`, `/flights`, `/auth/*`
  only — no update/delete endpoints.

## 💻 Legacy CLI Tool
The original terminal-based Python tool is preserved in `main.py` for legacy manual testing and direct database administration.

## 📝 License

MIT — see [LICENSE](LICENSE).
