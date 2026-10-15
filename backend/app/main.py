
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from starlette.datastructures import UploadFile

from app.nlp import analyze_report


app = FastAPI(
    title="CivicSense API",
    description="Public grievance management with local rules-based NLP assistance",
    version="1.0.0",
)

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
AUTH_DB = Path(__file__).resolve().parent.parent / "civicsense.sqlite3"
MAX_PHOTO_SIZE = 5 * 1024 * 1024
PASSWORD_ITERATIONS = 310_000
TOKEN_LIFETIME_SECONDS = 7 * 24 * 60 * 60
PHOTO_FORMATS = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Allow our React frontend to communicate with the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request format for a new civic complaint.
class ComplaintRequest(BaseModel):
    description: str = Field(
        min_length=5,
        max_length=3000,
        description="Describe the civic problem",
    )
    location: str = Field(
        min_length=2,
        max_length=200,
        description="Area or locality where the issue occurred",
    )
    language: Literal["auto", "english", "hindi", "gujarati"] = Field(
        default="auto",
        description="Language of the complaint: auto, English, Hindi, or Gujarati",
    )
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


def get_auth_db():
    connection = sqlite3.connect(AUTH_DB, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_db():
    with get_auth_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS auth_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        complaints_table = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'complaints'"
        ).fetchone()
        if complaints_table and "'resolved'" not in complaints_table["sql"]:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("ALTER TABLE complaints RENAME TO complaints_legacy")
            connection.execute("""
                CREATE TABLE complaints (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    description TEXT NOT NULL,
                    location TEXT NOT NULL,
                    language TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'unclassified',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'declined', 'resolved')),
                    created_at TEXT NOT NULL,
                    photo_url TEXT,
                    latitude REAL,
                    longitude REAL,
                    department TEXT,
                    response_due_at TEXT,
                    decline_reason TEXT
                )
            """)
            legacy_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(complaints_legacy)")
            }
            optional_columns = ("latitude", "longitude", "department", "response_due_at", "decline_reason")
            legacy_values = {
                column: column if column in legacy_columns else "NULL"
                for column in optional_columns
            }
            connection.execute(f"""
                INSERT INTO complaints (
                    id, user_id, description, location, language, category, priority,
                    status, created_at, photo_url, latitude, longitude, department,
                    response_due_at, decline_reason
                )
                SELECT id, user_id, description, location, language,
                       COALESCE(category, 'unclassified'),
                       CASE WHEN priority IN ('high', 'urgent', 'low') THEN priority ELSE 'normal' END,
                       CASE WHEN status = 'submitted' THEN 'pending' ELSE status END,
                       created_at, photo_url,
                       {legacy_values["latitude"]}, {legacy_values["longitude"]},
                       {legacy_values["department"]}, {legacy_values["response_due_at"]},
                       {legacy_values["decline_reason"]}
                FROM complaints_legacy
            """)
            connection.execute("DROP TABLE complaints_legacy")
            connection.execute("PRAGMA foreign_keys = ON")
        else:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS complaints (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    description TEXT NOT NULL,
                    location TEXT NOT NULL,
                    language TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'unclassified',
                    priority TEXT NOT NULL DEFAULT 'normal',
                    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'declined', 'resolved')),
                    created_at TEXT NOT NULL,
                    photo_url TEXT,
                    latitude REAL,
                    longitude REAL,
                    department TEXT,
                    response_due_at TEXT,
                    decline_reason TEXT
                )
            """)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(complaints)")}
            migrations = {
                "latitude": "REAL",
                "longitude": "REAL",
                "department": "TEXT",
                "response_due_at": "TEXT",
                "decline_reason": "TEXT",
            }
            for column, data_type in migrations.items():
                if column not in columns:
                    connection.execute(f"ALTER TABLE complaints ADD COLUMN {column} {data_type}")
        nlp_migrations = {
            "nlp_analyzed": "INTEGER NOT NULL DEFAULT 0",
            "detected_language": "TEXT NOT NULL DEFAULT 'unknown'",
            "language_confidence": "REAL NOT NULL DEFAULT 0",
            "suggested_category": "TEXT NOT NULL DEFAULT 'unclassified'",
            "category_confidence": "REAL NOT NULL DEFAULT 0",
            "category_matches_json": "TEXT NOT NULL DEFAULT '[]'",
            "urgency_flag": "INTEGER NOT NULL DEFAULT 0",
            "urgency_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
            "extractive_summary": "TEXT NOT NULL DEFAULT ''",
            "entities_json": "TEXT NOT NULL DEFAULT '[]'",
            "spam_flag": "INTEGER NOT NULL DEFAULT 0",
            "spam_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
            "duplicate_candidates_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(complaints)")}
        for column, data_type in nlp_migrations.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE complaints ADD COLUMN {column} {data_type}")
        connection.execute("""
            UPDATE complaints
            SET nlp_analyzed = 1
            WHERE nlp_analyzed = 0
              AND (
                  extractive_summary != ''
                  OR detected_language != 'unknown'
                  OR spam_reasons_json != '[]'
              )
        """)
        unanalyzed_complaints = connection.execute("""
            SELECT id, description, location, language
            FROM complaints
            WHERE nlp_analyzed = 0
        """).fetchall()
        for complaint in unanalyzed_complaints:
            analysis = analyze_report(
                complaint["description"],
                complaint["location"],
                complaint["language"],
            )
            connection.execute("""
                UPDATE complaints
                SET nlp_analyzed = 1,
                    detected_language = ?,
                    language_confidence = ?,
                    suggested_category = ?,
                    category_confidence = ?,
                    category_matches_json = ?,
                    urgency_flag = ?,
                    urgency_reasons_json = ?,
                    extractive_summary = ?,
                    entities_json = ?,
                    spam_flag = ?,
                    spam_reasons_json = ?,
                    duplicate_candidates_json = ?
                WHERE id = ?
            """, (
                analysis["detected_language"],
                analysis["language_confidence"],
                analysis["suggested_category"],
                analysis["category_confidence"],
                json.dumps(analysis["category_matches"], ensure_ascii=False),
                int(analysis["urgency_flag"]),
                json.dumps(analysis["urgency_reasons"], ensure_ascii=False),
                analysis["summary"],
                json.dumps(analysis["entities"], ensure_ascii=False),
                int(analysis["spam_flag"]),
                json.dumps(analysis["spam_reasons"], ensure_ascii=False),
                json.dumps(analysis["duplicate_candidates"], ensure_ascii=False),
                complaint["id"],
            ))
        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaint_events (
                id TEXT PRIMARY KEY,
                complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                user_id TEXT REFERENCES users(id),
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaint_updates (
                id TEXT PRIMARY KEY,
                complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaint_support (
                complaint_id TEXT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                PRIMARY KEY (complaint_id, user_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                complaint_id TEXT REFERENCES complaints(id) ON DELETE CASCADE,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                read_at TEXT
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS idx_complaints_user_created ON complaints(user_id, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_complaint_updates_complaint ON complaint_updates(complaint_id, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, read_at, created_at)")
        connection.execute("""
            INSERT INTO complaint_events (id, complaint_id, user_id, event_type, message, created_at)
            SELECT lower(hex(randomblob(16))), complaints.id, complaints.user_id,
                   'submitted', 'Report submitted', complaints.created_at
            FROM complaints
            WHERE NOT EXISTS (
                SELECT 1 FROM complaint_events WHERE complaint_id = complaints.id
            )
        """)
        if not os.environ.get("CIVICSENSE_AUTH_SECRET"):
            connection.execute(
                "INSERT OR IGNORE INTO auth_settings (key, value) VALUES (?, ?)",
                ("token_secret", secrets.token_urlsafe(48)),
            )
        admin_user_id = os.environ.get("CIVICSENSE_ADMIN_USER_ID")
        if admin_user_id:
            connection.execute(
                "INSERT OR REPLACE INTO auth_settings (key, value) VALUES (?, ?)",
                ("admin_user_id", admin_user_id.strip()),
            )


initialize_auth_db()


def auth_secret():
    configured_secret = os.environ.get("CIVICSENSE_AUTH_SECRET")
    if configured_secret:
        return configured_secret.encode("utf-8")
    with get_auth_db() as connection:
        row = connection.execute(
            "SELECT value FROM auth_settings WHERE key = ?",
            ("token_secret",),
        ).fetchone()
    if row is None:
        raise RuntimeError("CivicSense authentication secret is unavailable")
    return row["value"].encode("utf-8")


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password, stored_hash):
    salt_hex, digest_hex = stored_hash.split("$", maxsplit=1)
    candidate_hash = hash_password(password, bytes.fromhex(salt_hex)).split("$", maxsplit=1)[1]
    return hmac.compare_digest(candidate_hash, digest_hex)


def encode_token(user_id):
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": user_id,
        "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }, separators=(",", ":")).encode("utf-8")).rstrip(b"=")
    signature = hmac.new(auth_secret(), payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{payload.decode('ascii')}.{encoded_signature.decode('ascii')}"


def decode_token(token):
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        payload_bytes = encoded_payload.encode("ascii")
        supplied_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        expected_signature = hmac.new(auth_secret(), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(
            payload_bytes + b"=" * (-len(payload_bytes) % 4)
        ))
        if not isinstance(payload.get("sub"), str) or payload.get("exp", 0) <= time.time():
            return None
        return payload["sub"]
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return None


def public_user(row):
    configured_admin_id = os.environ.get("CIVICSENSE_ADMIN_USER_ID")
    if not configured_admin_id:
        with get_auth_db() as connection:
            admin_setting = connection.execute(
                "SELECT value FROM auth_settings WHERE key = ?",
                ("admin_user_id",),
            ).fetchone()
        configured_admin_id = admin_setting["value"] if admin_setting else ""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "created_at": row["created_at"],
        "is_admin": bool(configured_admin_id and row["id"] == configured_admin_id),
    }


class RegistrationRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value):
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower()


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


def validate_email(email):
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address")


def user_from_authorization(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to continue")
    user_id = decode_token(authorization[7:])
    if user_id is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again")
    with get_auth_db() as connection:
        user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Your account could not be found")
    return public_user(user)


def admin_from_authorization(authorization):
    user = user_from_authorization(authorization)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access is required")
    return user


def visible_duplicate_reports(connection, user_id):
    rows = connection.execute(
        """
        SELECT id, description, location, category
        FROM complaints
        WHERE status IN ('approved', 'resolved') OR user_id = ?
        ORDER BY created_at DESC
        LIMIT 500
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def deserialize_nlp_record(row):
    record = dict(row)
    for response_key, storage_key in (
        ("category_matches", "category_matches_json"),
        ("urgency_reasons", "urgency_reasons_json"),
        ("entities", "entities_json"),
        ("spam_reasons", "spam_reasons_json"),
        ("duplicate_candidates", "duplicate_candidates_json"),
    ):
        record[response_key] = json.loads(record.pop(storage_key, "[]"))
    record["urgency_flag"] = bool(record.get("urgency_flag"))
    record["spam_flag"] = bool(record.get("spam_flag"))
    record["nlp_analyzed"] = bool(record.get("nlp_analyzed", False))
    return record


@app.post("/auth/register", status_code=201)
def register(request: RegistrationRequest):
    email = request.email
    validate_email(email)
    if not request.name:
        raise HTTPException(status_code=422, detail="Enter your name")
    user_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with get_auth_db() as connection:
            connection.execute(
                "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, request.name, email, hash_password(request.password), created_at),
            )
            user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="An account with this email already exists") from error
    return {
        "message": "Your CivicSense account is ready",
        "token": encode_token(user_id),
        "user": public_user(user),
    }


@app.post("/auth/login")
def login(request: LoginRequest):
    email = request.email.strip().lower()
    validate_email(email)
    with get_auth_db() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
    if user is None or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {
        "message": "Signed in successfully",
        "token": encode_token(user["id"]),
        "user": public_user(user),
    }


@app.get("/auth/me")
def get_current_user(request: Request):
    return {"user": user_from_authorization(request.headers.get("authorization"))}


@app.get("/")
def home():
    return {
        "message": "Welcome to CivicSense!",
        "status": "running",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CivicSense API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/nlp/analyze")
def preview_nlp_analysis(complaint_request: ComplaintRequest, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        existing = visible_duplicate_reports(connection, user["id"])
    return analyze_report(
        complaint_request.description.strip(),
        complaint_request.location.strip(),
        complaint_request.language,
        existing,
    )


@app.post("/complaints", status_code=201)
async def create_complaint(request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    photo_url = None
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        async with request.form() as form:
            try:
                complaint_request = ComplaintRequest.model_validate({
                    "description": form.get("description"),
                    "location": form.get("location"),
                    "language": form.get("language", "auto"),
                    "latitude": form.get("latitude") or None,
                    "longitude": form.get("longitude") or None,
                })
            except ValidationError as error:
                raise HTTPException(status_code=422, detail=error.errors()) from error
            photo_value = form.get("photo")
            if photo_value is not None:
                if not isinstance(photo_value, UploadFile):
                    raise HTTPException(status_code=400, detail="Invalid photo upload")
                contents = await photo_value.read(MAX_PHOTO_SIZE + 1)
                if not contents:
                    raise HTTPException(status_code=400, detail="The uploaded photo is empty")
                if len(contents) > MAX_PHOTO_SIZE:
                    raise HTTPException(status_code=413, detail="Photos must be 5 MB or smaller")

                extension = next(
                    (extension for signature, extension in PHOTO_FORMATS.items()
                     if contents.startswith(signature)),
                    None,
                )
                if extension is None and len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
                    extension = ".webp"
                if extension is None:
                    raise HTTPException(
                        status_code=415,
                        detail="Use a JPG, PNG, or WebP image",
                    )

                photo_name = f"{uuid4().hex}{extension}"
                (UPLOAD_DIR / photo_name).write_bytes(contents)
                photo_url = f"/uploads/{photo_name}"
    elif request.headers.get("content-type", "").startswith("application/json"):
        try:
            try:
                payload = await request.json()
            except ValueError as error:
                raise HTTPException(status_code=400, detail="Invalid JSON body") from error
            complaint_request = ComplaintRequest.model_validate(payload)
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=error.errors()) from error
    else:
        raise HTTPException(
            status_code=415,
            detail="Submit the report as JSON or multipart form data",
        )

    complaint_id = str(uuid4())

    normalized_language = complaint_request.language.lower().strip()
    description = complaint_request.description.strip()
    location = complaint_request.location.strip()
    with get_auth_db() as connection:
        analysis = analyze_report(
            description,
            location,
            normalized_language,
            visible_duplicate_reports(connection, user["id"]),
        )

    complaint = {
        "id": complaint_id,
        "user_id": user["id"],
        "description": description,
        "location": location,
        "language": normalized_language,
        "category": "unclassified",
        "priority": "normal",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "photo_url": photo_url,
        "latitude": complaint_request.latitude,
        "longitude": complaint_request.longitude,
        "department": None,
        "response_due_at": None,
        "decline_reason": None,
    }

    with get_auth_db() as connection:
        connection.execute(
            """
            INSERT INTO complaints (
                id, user_id, description, location, language,
                category, priority, status, created_at, photo_url, latitude, longitude,
                detected_language, language_confidence, suggested_category,
                category_confidence, category_matches_json, urgency_flag,
                urgency_reasons_json, extractive_summary, entities_json, spam_flag,
                spam_reasons_json, duplicate_candidates_json, nlp_analyzed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint["id"],
                complaint["user_id"],
                complaint["description"],
                complaint["location"],
                complaint["language"],
                complaint["category"],
                complaint["priority"],
                complaint["status"],
                complaint["created_at"],
                complaint["photo_url"],
                complaint["latitude"],
                complaint["longitude"],
                analysis["detected_language"],
                analysis["language_confidence"],
                analysis["suggested_category"],
                analysis["category_confidence"],
                json.dumps(analysis["category_matches"], ensure_ascii=False),
                int(analysis["urgency_flag"]),
                json.dumps(analysis["urgency_reasons"], ensure_ascii=False),
                analysis["summary"],
                json.dumps(analysis["entities"], ensure_ascii=False),
                int(analysis["spam_flag"]),
                json.dumps(analysis["spam_reasons"], ensure_ascii=False),
                json.dumps(analysis["duplicate_candidates"], ensure_ascii=False),
                1,
            ),
        )
        connection.execute(
            """
            INSERT INTO complaint_events (id, complaint_id, user_id, event_type, message, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                complaint_id,
                user["id"],
                "submitted",
                "Report submitted",
                complaint["created_at"],
            ),
        )

    return {
        "message": "Complaint submitted successfully",
        "complaint": {key: value for key, value in complaint.items() if key != "user_id"},
        "analysis": analysis,
    }


@app.get("/complaints")
def get_complaints(request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        rows = connection.execute(
            """
            SELECT complaints.id, description, location, language, category, priority,
                   status, created_at, photo_url, latitude, longitude, department,
                   response_due_at, decline_reason,
                   detected_language, language_confidence, suggested_category,
                   category_confidence, category_matches_json, urgency_flag,
                   urgency_reasons_json, extractive_summary, entities_json,
                   spam_flag, spam_reasons_json, duplicate_candidates_json, nlp_analyzed,
                   (SELECT MAX(created_at) FROM complaint_events
                    WHERE complaint_id = complaints.id AND event_type = 'status'
                    AND message = 'Your report was marked resolved') AS resolved_at,
                   (SELECT COUNT(*) FROM complaint_support
                    WHERE complaint_id = complaints.id) AS support_count,
                   EXISTS(SELECT 1 FROM complaint_support
                          WHERE complaint_id = complaints.id AND user_id = ?) AS viewer_has_supported
            FROM complaints
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user["id"], user["id"]),
        ).fetchall()
    complaints = [deserialize_nlp_record(row) for row in rows]
    return {
        "total": len(complaints),
        "complaints": complaints,
    }


@app.get("/community/complaints")
def get_community_complaints(
    request: Request,
    search: str = Query(default="", max_length=100),
    location: str = Query(default="", max_length=200),
    category: str = Query(default="", max_length=80),
    status: Literal["", "pending", "approved", "declined", "resolved"] = "",
    priority: Literal["", "low", "normal", "high", "urgent"] = "",
    created_after: str = Query(default="", max_length=30),
    created_before: str = Query(default="", max_length=30),
):
    user = user_from_authorization(request.headers.get("authorization"))
    filters = []
    values = []
    if search.strip():
        filters.append("(description LIKE ? OR location LIKE ?)")
        values.extend((f"%{search.strip()}%", f"%{search.strip()}%"))
    if location.strip():
        filters.append("location LIKE ?")
        values.append(f"%{location.strip()}%")
    if category:
        filters.append("category = ?")
        values.append(category)
    if status:
        filters.append("status = ?")
        values.append(status)
    if priority:
        filters.append("priority = ?")
        values.append(priority)
    if created_after:
        filters.append("created_at >= ?")
        values.append(created_after)
    if created_before:
        filters.append("created_at < ?")
        values.append(created_before)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    ordering = "resolved_at DESC" if status == "resolved" else "CASE WHEN status = 'resolved' THEN 1 ELSE 0 END, created_at DESC"
    with get_auth_db() as connection:
        rows = connection.execute(
            f"""
            SELECT complaints.id, description, location, language, category, priority,
                   status, created_at, photo_url, latitude, longitude, department,
                   response_due_at, decline_reason,
                   (SELECT MAX(created_at) FROM complaint_events
                    WHERE complaint_id = complaints.id AND event_type = 'status'
                    AND message = 'Your report was marked resolved') AS resolved_at,
                   (SELECT COUNT(*) FROM complaint_support
                    WHERE complaint_id = complaints.id) AS support_count,
                   EXISTS(SELECT 1 FROM complaint_support
                          WHERE complaint_id = complaints.id AND user_id = ?) AS viewer_has_supported
            FROM complaints
            {where_clause}
            ORDER BY {ordering}
            LIMIT 200
            """,
            [user["id"], *values],
        ).fetchall()
    complaints = [dict(row) for row in rows]
    return {"total": len(complaints), "complaints": complaints}


@app.get("/admin/complaints")
def get_all_complaints(
    request: Request,
    search: str = Query(default="", max_length=100),
    status: Literal["", "pending", "approved", "declined", "resolved"] = "",
    priority: Literal["", "low", "normal", "high", "urgent"] = "",
    department: str = Query(default="", max_length=80),
):
    admin_from_authorization(request.headers.get("authorization"))
    filters = []
    values = []
    if search.strip():
        filters.append("(complaints.description LIKE ? OR complaints.location LIKE ? OR users.email LIKE ?)")
        values.extend((f"%{search.strip()}%", f"%{search.strip()}%", f"%{search.strip()}%"))
    if status:
        filters.append("complaints.status = ?")
        values.append(status)
    if priority:
        filters.append("complaints.priority = ?")
        values.append(priority)
    if department:
        filters.append("complaints.department = ?")
        values.append(department)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    with get_auth_db() as connection:
        rows = connection.execute(
            f"""
            SELECT complaints.id, complaints.description, complaints.location,
                   complaints.language, complaints.category, complaints.priority,
                   complaints.status, complaints.created_at, complaints.photo_url,
                   complaints.latitude, complaints.longitude, complaints.department,
                   complaints.response_due_at, complaints.decline_reason,
                   complaints.detected_language, complaints.language_confidence,
                   complaints.suggested_category, complaints.category_confidence,
                   complaints.category_matches_json, complaints.urgency_flag,
                   complaints.urgency_reasons_json, complaints.extractive_summary,
                   complaints.entities_json, complaints.spam_flag,
                   complaints.spam_reasons_json, complaints.duplicate_candidates_json,
                   complaints.nlp_analyzed,
                   (SELECT MAX(created_at) FROM complaint_events
                    WHERE complaint_id = complaints.id AND event_type = 'status'
                    AND message = 'Your report was marked resolved') AS resolved_at,
                   (SELECT COUNT(*) FROM complaint_support
                    WHERE complaint_id = complaints.id) AS support_count,
                   users.name AS reporter_name, users.email AS reporter_email
            FROM complaints
            JOIN users ON users.id = complaints.user_id
            {where_clause}
            ORDER BY
                CASE complaints.status WHEN 'pending' THEN 0 ELSE 1 END,
                complaints.created_at DESC
            """,
            values,
        ).fetchall()
    complaints = [deserialize_nlp_record(row) for row in rows]
    return {"total": len(complaints), "complaints": complaints}


class ComplaintReviewRequest(BaseModel):
    status: Literal["approved", "declined", "resolved"] | None = None
    category: Literal[
        "unclassified",
        "roads",
        "parks",
        "waste",
        "water",
        "street_lighting",
        "public_safety",
        "other",
    ] | None = None
    department: Literal[
        "Roads & Transport",
        "Parks & Recreation",
        "Waste Management",
        "Water & Drainage",
        "Street Lighting",
        "Public Safety",
        "Other",
    ] | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    response_hours: int | None = Field(default=None, ge=1, le=8760)
    decline_reason: str | None = Field(default=None, max_length=1000)


class ComplaintUpdateRequest(BaseModel):
    body: str = Field(min_length=3, max_length=1000)

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value):
        return value.strip()


def create_notification(connection, user_id, complaint_id, message, created_at):
    connection.execute(
        """
        INSERT INTO notifications (id, user_id, complaint_id, message, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (str(uuid4()), user_id, complaint_id, message, created_at),
    )


def add_complaint_event(connection, complaint_id, user_id, event_type, message, created_at):
    connection.execute(
        """
        INSERT INTO complaint_events (id, complaint_id, user_id, event_type, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (str(uuid4()), complaint_id, user_id, event_type, message, created_at),
    )


@app.patch("/admin/complaints/{complaint_id}")
def review_complaint(complaint_id: str, review: ComplaintReviewRequest, request: Request):
    admin = admin_from_authorization(request.headers.get("authorization"))
    supplied_fields = review.model_fields_set
    if not supplied_fields:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")
    if review.status == "declined" and (
        review.decline_reason is None or not review.decline_reason.strip()
    ):
        raise HTTPException(status_code=422, detail="Provide a reason when declining a report")
    now = datetime.now(timezone.utc)
    with get_auth_db() as connection:
        complaint = connection.execute(
            "SELECT * FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        old_status = complaint["status"]
        if review.status:
            allowed_transitions = {
                "pending": {"approved", "declined"},
                "approved": {"resolved"},
            }
            if review.status not in allowed_transitions.get(old_status, set()):
                raise HTTPException(status_code=409, detail="This status change is not allowed")

        assignments = []
        values = []
        if review.status is not None:
            assignments.append("status = ?")
            values.append(review.status)
            if review.status == "declined":
                assignments.append("decline_reason = ?")
                values.append(review.decline_reason.strip())
            elif "decline_reason" in supplied_fields:
                assignments.append("decline_reason = ?")
                values.append(None)
        if "category" in supplied_fields and review.category is not None:
            assignments.append("category = ?")
            values.append(review.category)
        if "department" in supplied_fields:
            assignments.append("department = ?")
            values.append(review.department)
        if "priority" in supplied_fields and review.priority is not None:
            assignments.append("priority = ?")
            values.append(review.priority)
        if "response_hours" in supplied_fields:
            due_at = (
                (now + timedelta(hours=review.response_hours)).isoformat()
                if review.response_hours is not None
                else None
            )
            assignments.append("response_due_at = ?")
            values.append(due_at)
        if assignments:
            values.append(complaint_id)
            connection.execute(
                f"UPDATE complaints SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
        if review.status and review.status != old_status:
            message = {
                "approved": "Your report was approved",
                "declined": "Your report was declined",
                "resolved": "Your report was marked resolved",
            }[review.status]
            if review.status == "declined":
                message += f": {review.decline_reason.strip()}"
            add_complaint_event(connection, complaint_id, admin["id"], "status", message, now.isoformat())
            create_notification(connection, complaint["user_id"], complaint_id, message, now.isoformat())
            connection.execute(
                """
                INSERT INTO notifications (id, user_id, complaint_id, message, created_at)
                SELECT lower(hex(randomblob(16))), complaint_support.user_id, ?, ?, ?
                FROM complaint_support
                WHERE complaint_id = ? AND user_id != ?
                """,
                (
                    complaint_id,
                    f"A report you support was {review.status}",
                    now.isoformat(),
                    complaint_id,
                    complaint["user_id"],
                ),
            )
        elif any(field in supplied_fields for field in ("category", "department", "priority", "response_hours")):
            add_complaint_event(
                connection,
                complaint_id,
                admin["id"],
                "assignment",
                "Report triage details updated",
                now.isoformat(),
            )
        complaint = connection.execute(
            """
            SELECT id, description, location, language, category, priority,
                   status, created_at, photo_url, latitude, longitude, department,
                   response_due_at, decline_reason
            FROM complaints WHERE id = ?
            """,
            (complaint_id,),
        ).fetchone()
    return {
        "message": f"Complaint {review.status or 'updated'}",
        "complaint": dict(complaint),
    }


@app.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        complaint = connection.execute(
            """
            SELECT id, description, location, language, category, priority,
                   status, created_at, photo_url, latitude, longitude,
                   department, response_due_at, decline_reason
            FROM complaints
            WHERE id = ? AND user_id = ?
            """,
            (complaint_id, user["id"]),
        ).fetchone()
    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found",
        )

    return dict(complaint)


@app.get("/community/complaints/{complaint_id}/timeline")
def get_complaint_timeline(complaint_id: str, request: Request):
    user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        complaint = connection.execute(
            "SELECT id FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        events = connection.execute(
            """
            SELECT complaint_events.id, complaint_events.event_type,
                   complaint_events.message, complaint_events.created_at,
                   users.name AS actor_name
            FROM complaint_events
            LEFT JOIN users ON users.id = complaint_events.user_id
            WHERE complaint_id = ?
            ORDER BY complaint_events.created_at ASC
            """,
            (complaint_id,),
        ).fetchall()
    return {"events": [dict(event) for event in events]}


@app.get("/community/complaints/{complaint_id}/updates")
def get_complaint_updates(complaint_id: str, request: Request):
    user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        exists = connection.execute(
            "SELECT 1 FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        updates = connection.execute(
            """
            SELECT complaint_updates.id, complaint_updates.body,
                   complaint_updates.created_at, users.name AS author_name
            FROM complaint_updates
            JOIN users ON users.id = complaint_updates.user_id
            WHERE complaint_id = ?
            ORDER BY complaint_updates.created_at ASC
            """,
            (complaint_id,),
        ).fetchall()
    return {"updates": [dict(update) for update in updates]}


@app.post("/community/complaints/{complaint_id}/updates", status_code=201)
def create_complaint_update(complaint_id: str, update: ComplaintUpdateRequest, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    now = datetime.now(timezone.utc).isoformat()
    update_id = str(uuid4())
    with get_auth_db() as connection:
        complaint = connection.execute(
            "SELECT user_id, status FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        if complaint["status"] in ("declined", "resolved"):
            raise HTTPException(status_code=409, detail="Updates are closed for this report")
        connection.execute(
            """
            INSERT INTO complaint_updates (id, complaint_id, user_id, body, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (update_id, complaint_id, user["id"], update.body, now),
        )
        add_complaint_event(
            connection,
            complaint_id,
            user["id"],
            "update",
            f"Community update from {user['name']}",
            now,
        )
        if complaint["user_id"] != user["id"]:
            create_notification(
                connection,
                complaint["user_id"],
                complaint_id,
                f"{user['name']} added an update to your report",
                now,
            )
        connection.execute(
            """
            INSERT INTO notifications (id, user_id, complaint_id, message, created_at)
            SELECT ?, complaint_support.user_id, ?, ?, ?
            FROM complaint_support
            WHERE complaint_id = ? AND user_id != ? AND user_id != ?
            """,
            (
                str(uuid4()),
                complaint_id,
                f"{user['name']} added an update to a report you support",
                now,
                complaint_id,
                user["id"],
                complaint["user_id"],
            ),
        )
    return {
        "update": {
            "id": update_id,
            "body": update.body,
            "created_at": now,
            "author_name": user["name"],
        }
    }


@app.post("/community/complaints/{complaint_id}/support")
def support_complaint(complaint_id: str, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    now = datetime.now(timezone.utc).isoformat()
    with get_auth_db() as connection:
        complaint = connection.execute(
            "SELECT user_id FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        connection.execute(
            "INSERT OR IGNORE INTO complaint_support (complaint_id, user_id, created_at) VALUES (?, ?, ?)",
            (complaint_id, user["id"], now),
        )
        count = connection.execute(
            "SELECT COUNT(*) AS total FROM complaint_support WHERE complaint_id = ?",
            (complaint_id,),
        ).fetchone()["total"]
    return {"supported": True, "support_count": count}


@app.delete("/community/complaints/{complaint_id}/support")
def unsupport_complaint(complaint_id: str, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        complaint = connection.execute(
            "SELECT 1 FROM complaints WHERE id = ?",
            (complaint_id,),
        ).fetchone()
        if complaint is None:
            raise HTTPException(status_code=404, detail="Complaint not found")
        connection.execute(
            "DELETE FROM complaint_support WHERE complaint_id = ? AND user_id = ?",
            (complaint_id, user["id"]),
        )
        count = connection.execute(
            "SELECT COUNT(*) AS total FROM complaint_support WHERE complaint_id = ?",
            (complaint_id,),
        ).fetchone()["total"]
    return {"supported": False, "support_count": count}


@app.get("/notifications")
def get_notifications(request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    with get_auth_db() as connection:
        rows = connection.execute(
            """
            SELECT id, complaint_id, message, created_at, read_at
            FROM notifications WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 100
            """,
            (user["id"],),
        ).fetchall()
        unread = connection.execute(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id = ? AND read_at IS NULL",
            (user["id"],),
        ).fetchone()["total"]
    return {"notifications": [dict(row) for row in rows], "unread": unread}


@app.patch("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    now = datetime.now(timezone.utc).isoformat()
    with get_auth_db() as connection:
        result = connection.execute(
            "UPDATE notifications SET read_at = COALESCE(read_at, ?) WHERE id = ? AND user_id = ?",
            (now, notification_id, user["id"]),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}


@app.post("/notifications/read-all")
def mark_all_notifications_read(request: Request):
    user = user_from_authorization(request.headers.get("authorization"))
    now = datetime.now(timezone.utc).isoformat()
    with get_auth_db() as connection:
        connection.execute(
            "UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
            (now, user["id"]),
        )
    return {"message": "Notifications marked as read"}
