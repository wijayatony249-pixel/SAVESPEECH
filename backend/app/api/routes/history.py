from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.api.deps import get_current_user, get_db
from app.db.models import User, AnalysisResult, AuditLog
from app.core.security import generate_ip_hash

router = APIRouter(prefix="/history", tags=["History"])


class HistoryItem(BaseModel):
    id: str
    job_id: str
    label: str
    scam_category: Optional[str] = None
    risk_score: int
    risk_level: str
    explanation: str
    created_at: str

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int
    page: int
    page_size: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("", response_model=HistoryResponse)
def get_user_history(
    request: Request,
    page: int = Query(1, ge=1, description="Nomor halaman"),
    pageSize: int = Query(10, ge=1, le=50, description="Jumlah data per halaman"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HistoryResponse:
    """Mengambil riwayat analisis tersimpan (opt-in) dengan paginasi.
    Secara otomatis membersihkan entri yang sudah kedaluwarsa (> 30 hari).
    """
    now = datetime.now(timezone.utc)

    # 1. Pembersihan otomatis entri yang kedaluwarsa
    db.query(AnalysisResult).filter(
        AnalysisResult.expires_at.isnot(None),
        AnalysisResult.expires_at < now
    ).delete(synchronize_session=False)
    db.commit()

    # 2. Query data riwayat milik user aktif
    query = db.query(AnalysisResult).filter(AnalysisResult.user_id == current_user.id)
    total = query.count()

    offset = (page - 1) * pageSize
    records = query.order_by(AnalysisResult.created_at.desc()).offset(offset).limit(pageSize).all()

    items = [
        HistoryItem(
            id=str(r.id),
            job_id=r.job_id,
            label=r.label,
            scam_category=r.scam_category,
            risk_score=r.risk_score,
            risk_level=r.risk_level,
            explanation=r.explanation,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in records
    ]

    # 3. Catat audit akses riwayat
    ip = _get_client_ip(request)
    audit = AuditLog(
        user_id=current_user.id,
        action="view_history",
        status="success",
        ip_hash=generate_ip_hash(ip),
    )
    db.add(audit)
    db.commit()

    return HistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=pageSize,
    )
