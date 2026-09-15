# Air-Travel Cargo Services Database Engine 🚀

A robust, production-ready logistics database engine and REST API serving a normalized MySQL schema. This system tracks complex supply chain networks with strict ACID transaction management and JWT-based role-based access control.

**Project period:** Apr -- May 2025 — built as a Database Management Systems course project.
This repository was published later, so the commit history postdates the original work.

## 🏗️ Architecture

- **Backend Framework**: FastAPI (Python)
- **Database**: MySQL 8.0 (Relational Database)
- **Deployment**: Docker & Docker Compose
- **Security**: Signed HS256 JWTs with role-based access control (admin / agent / viewer)

## ✨ Key Features

1. **ACID-Compliant Transactions**: Handles multi-table inserts (Cargo, Booking, Tracking History) with `conn.commit()` and `conn.rollback()` to ensure zero data corruption during logistics updates.
2. **Referential Integrity**: Implements strict `ON DELETE CASCADE` foreign key constraints across a normalized 5-table schema.
3. **Complex JOINs**: Real-time aggregation of cargo status, customer data, and flight manifests via normalized query mapping.
4. **REST API**: Exposes core functionality via `/cargo`, `/shipments/{id}` and `/flights` endpoints.
5. **JWT + RBAC Security**: Signed, expiring bearer tokens issued by `/auth/login`, with per-endpoint role enforcement and PBKDF2-hashed passwords — covered by a 10-case test suite.

## 🚀 Getting Started (Docker)

The entire application is containerized. You can spin up both the FastAPI web server and the MySQL database with a single command:

```bash
docker-compose up --build -d
```

Once running:
- **API Docs (Swagger UI)**: http://localhost:8000/docs
- **API Host**: http://localhost:8000

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

`test_auth.py` covers the auth and RBAC paths (signature validation, expiry, tampering,
role enforcement, password storage) and needs **no running database**:

```bash
python test_auth.py     # or: pytest test_auth.py -v
```

All 10 tests pass.

## 💻 Legacy CLI Tool
The original terminal-based Python tool is preserved in `main.py` for legacy manual testing and direct database administration.
