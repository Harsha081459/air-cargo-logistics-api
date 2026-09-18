from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
import mysql.connector
import os
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

app = FastAPI(
    title="Air-Travel Cargo Services API",
    description="RESTful logistics API with ACID transactions and JWT role-based access control",
    version="1.1.0"
)

# ====================== DATABASE CONNECTION ======================
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME", "air_cargo"),
            autocommit=False
        )
    except mysql.connector.Error:
        raise HTTPException(status_code=503, detail="Database unavailable")

# ====================== JWT AUTH & RBAC ======================
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "60"))
PBKDF2_ITERATIONS = 100_000

bearer_scheme = HTTPBearer(description="Paste the token returned by POST /auth/login")


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()


def _seed_user(password: str, role: str) -> dict:
    """Salt + hash a password at startup so no plaintext credential is ever stored."""
    salt = secrets.token_hex(16)
    return {"salt": salt, "password_hash": _hash_password(password, salt), "role": role}


# Demo credential store. A production deployment would back this with a `users` table;
# passwords are read from the environment and are never held in plaintext after startup.
USERS = {
    "admin": _seed_user(os.getenv("ADMIN_PASSWORD", "admin123"), "admin"),
    "agent": _seed_user(os.getenv("AGENT_PASSWORD", "agent123"), "agent"),
    "viewer": _seed_user(os.getenv("VIEWER_PASSWORD", "viewer123"), "viewer"),
}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS.get(username)
    if user is None:
        # Hash anyway so a missing user costs the same time as a wrong password.
        _hash_password(password, "dummy-salt")
        return None
    candidate = _hash_password(password, user["salt"])
    if not hmac.compare_digest(candidate, user["password_hash"]):
        return None
    return {"username": username, "role": user["role"]}


def create_access_token(username: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Validate the bearer token's HS256 signature and expiry."""
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "role", "iat", "exp"]},
        )
        if payload.get("sub") not in USERS or payload.get("role") != USERS[payload["sub"]]["role"]:
            raise jwt.InvalidTokenError("Unknown identity or role")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": payload.get("sub"), "role": payload.get("role")}


def require_role(*allowed_roles: str):
    """Dependency factory enforcing role-based access on an endpoint."""

    def _check(user: dict = Depends(verify_jwt_token)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user['role']}' is not permitted to perform this action",
            )
        return user

    return _check

# ====================== SCHEMAS ======================
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class CargoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)

    tracking_number: str = Field(min_length=1, max_length=20)
    weight: float = Field(gt=0, le=1e9)
    cargo_type: str = Field(min_length=1, max_length=50)
    total_cost: float = Field(ge=0, le=1e12)
    current_status: str = Field(min_length=1, max_length=50)
    current_location: str = Field(min_length=1, max_length=100)
    customer_id: str = Field(min_length=1, max_length=20)
    flight_id: str = Field(min_length=1, max_length=20)

# ====================== ENDPOINTS ======================

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "air-cargo-api"}


@app.post("/auth/login", response_model=TokenResponse)
def login(credentials: LoginRequest):
    """Exchange username/password for a signed, time-limited JWT."""
    user = authenticate_user(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(
        access_token=create_access_token(user["username"], user["role"]),
        expires_in=JWT_TTL_MINUTES * 60,
        role=user["role"],
    )


@app.get("/auth/me")
def read_current_user(user: dict = Depends(verify_jwt_token)):
    """Echo the identity encoded in the presented token."""
    return user

@app.get("/shipments/{tracking_id}")
def get_shipment_details(
    tracking_id: str,
    user: dict = Depends(require_role("admin", "agent", "viewer")),
):
    """
    GET /shipments/{id} with JOIN queries to fetch cargo, customer, and flight details.
    Readable by any authenticated role.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT 
                c.TrackingNumber, c.Weight, c.CargoType, c.CurrentStatus, c.CurrentLocation,
                cust.Name AS CustomerName, cust.Email,
                f.FlightID, f.OriginHub, f.DestinationHub, f.DepartureDate,
                b.BookingDate
            FROM cargo c
            LEFT JOIN booking b ON c.TrackingNumber = b.TrackingNumber
            LEFT JOIN customer cust ON b.CustomerID = cust.CustomerID
            LEFT JOIN flight f ON b.FlightID = f.FlightID
            WHERE c.TrackingNumber = %s
        """
        cursor.execute(query, (tracking_id,))
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Shipment not found")
            
        return {"data": result}
    finally:
        cursor.close()
        conn.close()

@app.get("/flights")
def get_available_flights(
    user: dict = Depends(require_role("admin", "agent", "viewer")),
):
    """
    GET /flights to retrieve available flight schedules and capacities.
    Readable by any authenticated role.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = """
            SELECT FlightID, OriginHub, DestinationHub, DepartureDate, AvailableCapacity
            FROM flight
            WHERE AvailableCapacity > 0
            ORDER BY DepartureDate ASC
        """
        cursor.execute(query)
        result = cursor.fetchall()
        
        return {"data": result}
    finally:
        cursor.close()
        conn.close()

@app.post("/cargo", status_code=201)
def create_cargo(
    cargo: CargoCreate,
    user: dict = Depends(require_role("admin", "agent")),
):
    """
    POST /cargo with strict ACID transaction management across multiple tables.
    Write access is restricted to the admin and agent roles; viewers get 403.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE flight SET AvailableCapacity = AvailableCapacity - %s
            WHERE FlightID = %s AND AvailableCapacity >= %s
        """, (cargo.weight, cargo.flight_id, cargo.weight))
        if cursor.rowcount != 1:
            raise HTTPException(status_code=409, detail="Flight unavailable or insufficient capacity")

        # Step 1: Insert into Cargo
        cursor.execute("""
            INSERT INTO cargo (TrackingNumber, Weight, CargoType, TotalCost, CurrentStatus, CurrentLocation)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (cargo.tracking_number, cargo.weight, cargo.cargo_type, cargo.total_cost, cargo.current_status, cargo.current_location))
        
        # Step 2: Create Booking mapping
        booking_id = f"BKG-{secrets.token_hex(8)}"
        cursor.execute("""
            INSERT INTO booking (BookingID, TrackingNumber, CustomerID, FlightID)
            VALUES (%s, %s, %s, %s)
        """, (booking_id, cargo.tracking_number, cargo.customer_id, cargo.flight_id))
        
        # Step 3: Insert Initial Tracking History
        cursor.execute("""
            INSERT INTO trackinghistory (TrackingNumber, Status, Location, Remarks)
            VALUES (%s, %s, %s, %s)
        """, (cargo.tracking_number, cargo.current_status, cargo.current_location, "Initial cargo booking via API"))
        
        # If all successful, commit transaction (ACID)
        conn.commit()
        
        return {
            "message": "Cargo created successfully", 
            "tracking_number": cargo.tracking_number,
            "booking_id": booking_id
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except mysql.connector.IntegrityError as err:
        conn.rollback()
        if err.errno == 1062:
            raise HTTPException(status_code=409, detail="Cargo or booking already exists")
        raise HTTPException(status_code=400, detail="Invalid customer or booking reference")
    except mysql.connector.Error:
        conn.rollback()
        raise HTTPException(status_code=503, detail="Booking failed; transaction rolled back")
    finally:
        cursor.close()
        conn.close()
