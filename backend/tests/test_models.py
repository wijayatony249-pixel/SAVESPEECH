import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import User, AnalysisResult, AnalysisIndicator, AuditLog, ModelVersion

# Database test in-memory SQLite terpisah
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(TEST_DATABASE_URL)


# Aktifkan Foreign Key cascade pada SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Fixture untuk membuat skema baru dan sesi database per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_insert_valid_entities(db_session):
    """Menguji penambahan data valid ke seluruh 5 model database."""
    # 1. User
    user = User(
        nama="Budi Santoso",
        email="budi@example.com",
        password_hash="hashed_pw_12345",
        role="user"
    )
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert user.role == "user"

    # 2. AnalysisResult
    result = AnalysisResult(
        user_id=user.id,
        job_id=str(uuid.uuid4()),
        label="SCAM",
        scam_category="BANK_IMPERSONATION",
        risk_score=90,
        risk_level="Critical",
        explanation="Terindikasi penipuan perbankan dengan meminta data kredensial.",
        expires_at=datetime.now(timezone.utc)
    )
    db_session.add(result)
    db_session.commit()
    assert result.id is not None
    assert result.risk_score == 90

    # 3. AnalysisIndicator
    indicator = AnalysisIndicator(
        result_id=result.id,
        indicator_code="REQ_OTP",
        weight=30
    )
    db_session.add(indicator)
    db_session.commit()
    assert indicator.id is not None

    # 4. AuditLog
    audit = AuditLog(
        user_id=user.id,
        action="login_success",
        status="success",
        ip_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    db_session.add(audit)
    db_session.commit()
    assert audit.id is not None

    # 5. ModelVersion
    m_ver = ModelVersion(
        name="savespeech_tfidf_linearsvc",
        version="v1.0.0",
        metrics_json={"recall_scam": 0.94, "wer": 0.18}
    )
    db_session.add(m_ver)
    db_session.commit()
    assert m_ver.id is not None


def test_constraint_invalid_label(db_session):
    """Constraint check: label di luar ('NORMAL', 'SUSPICIOUS', 'SCAM') harus ditolak."""
    user = User(nama="Tes User", email="tes@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()

    invalid_result = AnalysisResult(
        user_id=user.id,
        job_id="job-123",
        label="FRAUD",  # Invalid
        risk_score=50,
        risk_level="Medium",
        explanation="Tes"
    )
    db_session.add(invalid_result)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_constraint_invalid_risk_score(db_session):
    """Constraint check: risk_score di luar rentang 0-100 harus ditolak."""
    user = User(nama="Tes User 2", email="tes2@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()

    # Negatif
    res_neg = AnalysisResult(
        user_id=user.id,
        job_id="job-neg",
        label="SCAM",
        risk_score=-5,  # Invalid
        risk_level="Low",
        explanation="Tes"
    )
    db_session.add(res_neg)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Lebih dari 100
    res_over = AnalysisResult(
        user_id=user.id,
        job_id="job-over",
        label="SCAM",
        risk_score=105,  # Invalid
        risk_level="Critical",
        explanation="Tes"
    )
    db_session.add(res_over)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_constraint_invalid_risk_level(db_session):
    """Constraint check: risk_level di luar ('Low', 'Medium', 'High', 'Critical') harus ditolak."""
    user = User(nama="Tes User 3", email="tes3@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()

    invalid_level = AnalysisResult(
        user_id=user.id,
        job_id="job-level",
        label="SCAM",
        risk_score=80,
        risk_level="Dangerous",  # Invalid
        explanation="Tes"
    )
    db_session.add(invalid_level)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_cascade_delete(db_session):
    """Menguji bahwa menghapus user akan menghapus analysis_results dan analysis_indicators secara cascade."""
    user = User(nama="User Cascade", email="cascade@example.com", password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()

    res = AnalysisResult(
        user_id=user.id,
        job_id="job-cascade",
        label="SCAM",
        risk_score=95,
        risk_level="Critical",
        explanation="Tes cascade"
    )
    db_session.add(res)
    db_session.commit()

    ind = AnalysisIndicator(result_id=res.id, indicator_code="REQ_PIN", weight=30)
    db_session.add(ind)
    db_session.commit()

    res_id = res.id
    ind_id = ind.id

    # Hapus user
    db_session.delete(user)
    db_session.commit()

    # Pastikan result dan indicator ikut terhapus
    assert db_session.query(AnalysisResult).filter(AnalysisResult.id == res_id).first() is None
    assert db_session.query(AnalysisIndicator).filter(AnalysisIndicator.id == ind_id).first() is None


def test_no_audio_or_transcript_columns_in_db(db_session):
    """Audit Keamanan Data: Memastikan tidak ada kolom transkrip, kutipan, atau audio pada database."""
    forbidden_terms = ["audio", "transcript", "transkrip", "quote", "kutipan"]

    for table_name in ["analysis_results", "analysis_indicators"]:
        table = Base.metadata.tables[table_name]
        column_names = [col.name.lower() for col in table.columns]
        for col in column_names:
            for term in forbidden_terms:
                assert term not in col, f"Pelanggaran privasi: Kolom '{col}' ditemukan pada tabel '{table_name}'!"
