from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.db.models import User
from app.services.job_manager import job_manager
from app.schemas.analysis import JobStatusResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{jobId}", response_model=JobStatusResponse)
def get_job_status(jobId: str, current_user: User = Depends(get_current_user)) -> JobStatusResponse:
    """Mengambil status pemrosesan analisis pekerjaan berdasarkan jobId.
    Hanya pemilik pekerjaan yang dapat mengakses (selain itu dijawab 404 untuk mitigasi IDOR).
    """
    job = job_manager.get_job(jobId, str(current_user.id))
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        error_message=job.get("error_message"),
    )
