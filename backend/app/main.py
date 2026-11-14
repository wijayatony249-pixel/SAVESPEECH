from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.routes import health, auth, analyze, jobs, results, history

# Inisialisasi logging terstruktur
setup_logging(level="INFO" if settings.APP_ENV != "development" else "DEBUG")
logger = logging.getLogger("savespeech.main")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware untuk menambahkan HTTP security headers pada setiap respons."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler untuk startup dan shutdown."""
    logger.info("Memulai aplikasi SAVESPEECH Backend...")
    # Pastikan direktori temporer audio ada
    _ = settings.temp_dir_path
    yield
    logger.info("Mematikan aplikasi SAVESPEECH Backend...")


app = FastAPI(
    title="SAVESPEECH Backend API",
    description="API dan Pipeline AI untuk Sistem Deteksi Panggilan Penipuan Impersonasi Finansial",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. Pasang Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 2. Pasang CORS Middleware (khusus domain terdaftar, tanpa wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


# 3. Global Exception Handler sesuai kontrak JSON { error: { code, message } }
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    code = exc.status_code
    message = str(detail)

    # Tangani jika detail berbentuk dict
    if isinstance(detail, dict):
        code = detail.get("code", exc.status_code)
        message = detail.get("message", "Terjadi kesalahan HTTP")

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Buat pesan ringkas Bahasa Indonesia tanpa membuka stack trace
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    msg = first_error.get("msg", "Data tidak valid")
    error_message = f"Validasi gagal pada {loc}: {msg}" if loc else f"Validasi gagal: {msg}"

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": 422, "message": error_message}},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error occurred:")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Terjadi kesalahan internal pada server. Silakan coba beberapa saat lagi.",
            }
        },
    )


# 4. Registrasi Router dengan prefix /api
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(analyze.router, prefix="/api", tags=["Analyze"])
app.include_router(jobs.router, prefix="/api", tags=["Jobs"])
app.include_router(results.router, prefix="/api", tags=["Results"])
app.include_router(history.router, prefix="/api", tags=["History"])
