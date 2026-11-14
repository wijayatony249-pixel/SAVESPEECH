import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import Settings

client = TestClient(app)


def test_health_endpoint():
    """Menguji endpoint /api/health mengembalikan 200 dan format data yang benar."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "time" in data


def test_docs_available():
    """Menguji apakah swagger UI (/docs) dapat diakses."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "html" in response.text.lower()


def test_security_headers():
    """Menguji keberadaan HTTP Security Headers wajib."""
    response = client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_cors_allowed_origin():
    """Menguji bahwa origin yang terdaftar (http://localhost:5173) diizinkan."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin():
    """Menguji bahwa origin liar / asing tidak diizinkan."""
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://evil-site.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "http://evil-site.com"


def test_global_error_handler_not_found():
    """Menguji format response error global { error: { code, message } }."""
    response = client.get("/api/rute_tidak_ada_12345")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
    assert data["error"]["code"] == 404


def test_jwt_secret_validation_in_production():
    """Menguji validasi panjang JWT_SECRET minimal 32 karakter di luar mode dev."""
    with pytest.raises(ValueError, match="JWT_SECRET wajib memiliki panjang minimal 32 karakter"):
        Settings(APP_ENV="production", JWT_SECRET="short_secret")
