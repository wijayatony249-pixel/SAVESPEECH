import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
    JSON,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """Tabel pengguna sistem SAVESPEECH."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relasi
    results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user"
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="chk_users_role"),
    )


class AnalysisResult(Base):
    """Tabel ringkasan hasil analisis risiko (hanya untuk pengguna yang opt-in simpan riwayat).
    Catatan keamanan: TIDAK MENYIMPAN audio maupun transkrip mentah.
    """
    __tablename__ = "analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    scam_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relasi
    user: Mapped["User"] = relationship("User", back_populates="results")
    indicators: Mapped[List["AnalysisIndicator"]] = relationship(
        "AnalysisIndicator",
        back_populates="result",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "label IN ('NORMAL', 'SUSPICIOUS', 'SCAM')",
            name="chk_analysis_results_label"
        ),
        CheckConstraint(
            "risk_level IN ('Low', 'Medium', 'High', 'Critical')",
            name="chk_analysis_results_risk_level"
        ),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="chk_analysis_results_risk_score"
        ),
        CheckConstraint(
            "scam_category IS NULL OR scam_category IN ("
            "'BANK_IMPERSONATION', 'E_WALLET_IMPERSONATION', "
            "'OTP_SCAM', 'TRANSFER_SCAM', 'ACCOUNT_BLOCKING_SCAM')",
            name="chk_analysis_results_scam_category"
        ),
    )


class AnalysisIndicator(Base):
    """Tabel kode indikator dan bobot yang terdeteksi.
    Catatan keamanan: TANPA kolom kutipan atau transkrip teks percakapan.
    """
    __tablename__ = "analysis_indicators"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("analysis_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    indicator_code: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relasi
    result: Mapped["AnalysisResult"] = relationship("AnalysisResult", back_populates="indicators")


class AuditLog(Base):
    """Tabel pencatatan jejak audit sistem.
    Catatan keamanan: ip_hash berupa HMAC-SHA256 dari IP; tanpa email, password, atau transkrip.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relasi
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )


class ModelVersion(Base):
    """Tabel riwayat dan metadata versi model klasifikasi ML."""
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    metrics_json: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False
    )
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
