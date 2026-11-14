import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.api.deps import get_db
from app.core.config import settings
from app.services.job_manager import job_manager
from app.services.stt import WhisperModelSingleton

# Engine SQLite in-memory tunggal dengan StaticPool
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Pastikan SessionLocal di seluruh aplikasi terhubung ke database in-memory selama pengujian
import app.db.session as _db_session_mod
import app.services.pipeline as _pipeline_mod

_db_session_mod.SessionLocal = TestingSessionLocal
_pipeline_mod.SessionLocal = TestingSessionLocal


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pasang override global untuk seluruh test
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup dan teardown skema database serta folder temporer untuk setiap unit test."""
    Base.metadata.create_all(bind=test_engine)
    job_manager.clear()
    WhisperModelSingleton.reset()
    # Bersihkan file temporer sebelum test
    for f in settings.temp_dir_path.iterdir():
        if f.is_file():
            f.unlink(missing_ok=True)
    yield
    # Bersihkan database dan file temporer setelah test
    Base.metadata.drop_all(bind=test_engine)
    job_manager.clear()
    WhisperModelSingleton.reset()
    for f in settings.temp_dir_path.iterdir():
        if f.is_file():
            f.unlink(missing_ok=True)


@pytest.fixture
def db_session():
    """Fixture sesi database untuk pengujian ORM langsung."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client():
    """Fixture TestClient FastAPI."""
    with TestClient(app) as c:
        yield c
