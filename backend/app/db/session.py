from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# Inisialisasi engine database
# Pool pre-ping memastikan koneksi yang putus di pool diperbarui otomatis
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=(settings.APP_ENV == "development")
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI untuk mengelola sesi database dan menutupnya dengan aman."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
