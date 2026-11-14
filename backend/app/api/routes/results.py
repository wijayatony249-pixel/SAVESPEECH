import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User, AnalysisResult, AuditLog
from app.services.job_manager import job_manager
from app.core.security import generate_ip_hash
from app.schemas.analysis import ResultResponse

router = APIRouter(prefix="/results", tags=["Results"])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


@router.get("/{jobId}", response_model=ResultResponse)
def get_job_result(jobId: str, current_user: User = Depends(get_current_user)) -> ResultResponse:
    """Mengambil hasil lengkap analisis (in-memory) berdasarkan jobId.
    Hanya pemilik pekerjaan yang dapat mengakses saat status 'done'.
    """
    job = job_manager.get_job(jobId, str(current_user.id))

    if job["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hasil analisis belum siap. Status saat ini: '{job['status']}'.",
        )

    result_data = job.get("result")
    if not result_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hasil analisis tidak ditemukan di memori",
        )

    return ResultResponse(**result_data)


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_saved_result(
    id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Menghapus data riwayat analisis tersimpan (opt-in) dari database milik pengguna."""
    try:
        record_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data riwayat tidak ditemukan",
        )

    record = db.query(AnalysisResult).filter(AnalysisResult.id == record_id).first()
    # Mitigasi IDOR: Jika bukan milik pengguna aktif, jawab 404 (bukan 403)
    if not record or record.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data riwayat tidak ditemukan",
        )

    db.delete(record)

    # Catat ke audit log tanpa isi percakapan
    ip = _get_client_ip(request)
    audit = AuditLog(
        user_id=current_user.id,
        action="delete_history_result",
        status="success",
        ip_hash=generate_ip_hash(ip),
    )
    db.add(audit)
    db.commit()

    return {"status": "ok", "message": "Riwayat analisis berhasil dihapus"}
