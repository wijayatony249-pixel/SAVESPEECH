import uuid
from datetime import timedelta
import pytest
from app.db.models import User, AuditLog
from app.core.security import create_access_token
from app.core.limiter import limiter


def test_register_login_me_success(client):
    """Menguji alur lengkap: register -> login -> get profile (/me) berhasil."""
    payload = {
        "nama": "Ahmad Dani",
        "email": "Ahmad.Dani@Example.COM",
        "password": "Password123",
    }
    # 1. Register
    reg_res = client.post("/api/auth/register", json=payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "token" in reg_data
    assert "user" in reg_data
    assert reg_data["user"]["nama"] == "Ahmad Dani"
    assert reg_data["user"]["email"] == "ahmad.dani@example.com"  # Ter-normalisasi lowercase
    assert "password" not in reg_data["user"]
    assert "password_hash" not in reg_data["user"]

    token = reg_data["token"]

    # 2. Login
    login_res = client.post("/api/auth/login", json={
        "email": "ahmad.dani@example.com",
        "password": "Password123"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "token" in login_data
    assert login_data["user"]["email"] == "ahmad.dani@example.com"

    # 3. GET /me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["id"] == reg_data["user"]["id"]
    assert me_data["email"] == "ahmad.dani@example.com"


def test_register_duplicate_email(client):
    """Menguji bahwa pendaftaran dengan email duplikat mengembalikan 409."""
    payload = {
        "nama": "User Satu",
        "email": "duplikat@example.com",
        "password": "Password123",
    }
    res1 = client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"]["code"] == 409
    assert "sudah terdaftar" in data["error"]["message"].lower()


def test_register_weak_password(client):
    """Menguji bahwa kata sandi yang tidak memenuhi kebijakan ditolak (422)."""
    # Kurang dari 8 karakter
    res1 = client.post("/api/auth/register", json={"nama": "A", "email": "a@ex.com", "password": "Pass1"})
    assert res1.status_code == 422

    # Tanpa huruf besar
    res2 = client.post("/api/auth/register", json={"nama": "A", "email": "a@ex.com", "password": "password123"})
    assert res2.status_code == 422

    # Tanpa angka
    res3 = client.post("/api/auth/register", json={"nama": "A", "email": "a@ex.com", "password": "PasswordAbc"})
    assert res3.status_code == 422


def test_login_identical_error_message(client):
    """Menguji mitigasi user enumeration: pesan error identik untuk email salah vs password salah."""
    # Daftar 1 user valid
    client.post("/api/auth/register", json={"nama": "User A", "email": "valid@example.com", "password": "Password123"})

    # Email tidak terdaftar
    res_wrong_email = client.post("/api/auth/login", json={"email": "notfound@example.com", "password": "Password123"})
    assert res_wrong_email.status_code == 401

    # Email terdaftar tapi password salah
    res_wrong_pw = client.post("/api/auth/login", json={"email": "valid@example.com", "password": "WrongPassword123"})
    assert res_wrong_pw.status_code == 401

    assert res_wrong_email.json()["error"]["message"] == res_wrong_pw.json()["error"]["message"]
    assert res_wrong_email.json()["error"]["message"] == "Email atau kata sandi salah"


def test_expired_and_invalid_token(client):
    """Menguji penolakan token yang kedaluwarsa atau tidak valid."""
    # Token kedaluwarsa
    expired_token = create_access_token(subject=str(uuid.uuid4()), expires_delta=timedelta(seconds=-10))
    res_exp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp.status_code == 401
    assert "kedaluwarsa" in res_exp.json()["error"]["message"].lower()

    # Token rusak / string acak
    res_inv = client.get("/api/auth/me", headers={"Authorization": "Bearer token_palsu_12345"})
    assert res_inv.status_code == 401
    assert "tidak valid" in res_inv.json()["error"]["message"].lower()

    # Tanpa header Authorization
    res_none = client.get("/api/auth/me")
    assert res_none.status_code == 401


def test_audit_log_redaction(client, db_session):
    """Menguji bahwa audit log tersimpan dengan ip_hash HMAC-SHA256 tanpa mencatat password."""
    client.post("/api/auth/register", json={"nama": "Audit User", "email": "audit@example.com", "password": "SecretPassword123"})

    logs = db_session.query(AuditLog).all()
    assert len(logs) > 0
    for log in logs:
        assert len(log.ip_hash) == 64  # SHA-256 menghasilkan 64 hex characters
        assert log.action in ["register", "login_success", "login_failed"]


def test_login_rate_limiting(client):
    """Menguji slowapi rate limiting: maksimal 5 login per menit per IP."""
    limiter.reset()
    # 5 request pertama diizinkan (meskipun 401 karena salah password)
    for _ in range(5):
        res = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "WrongPassword123"})
        assert res.status_code == 401

    # Request ke-6 harus terkena 429 Too Many Requests
    res_limit = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "WrongPassword123"})
    assert res_limit.status_code == 429
    data = res_limit.json()
    assert data["error"]["code"] == 429
    assert "terlalu banyak permintaan" in data["error"]["message"].lower()
