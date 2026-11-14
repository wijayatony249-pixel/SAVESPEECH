import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, BackgroundTasks, HTTPException, Request, status

from app.core.limiter import limiter
from app.api.deps import get_current_user
from app.db.models import User
from app.services.upload_validation import validate_and_save_upload, validate_audio_duration
from app.services.storage import generate_temp_path, delete_file
from app.services.job_manager import job_manager
from app.services.pipeline import run_pipeline
from app.schemas.analysis import AnalyzeResponse

router = APIRouter(tags=["Analyze"])


@router.post("/analyze", response_model=AnalyzeResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def analyze_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    saveHistory: Optional[bool] = Form(False),
    current_user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    """Menerima unggahan audio dan memulai proses analisis asinkron."""
    orig_name = file.filename or ""
    _, ext = os.path.splitext(orig_name.lower())

    temp_path = generate_temp_path(ext)

    try:
        # 1. Streaming validation & save
        await validate_and_save_upload(file, temp_path)

        # 2. Validasi durasi via ffprobe
        duration = validate_audio_duration(temp_path)

        # 3. Buat job di in-memory job manager
        job_id = job_manager.create_job(str(current_user.id))

        # 4. Jadwalkan pipeline di background
        background_tasks.add_task(
            run_pipeline,
            job_id=job_id,
            file_path=temp_path,
            user_id=str(current_user.id),
            save_history=bool(saveHistory),
            duration=duration,
        )

        return AnalyzeResponse(job_id=job_id)

    except Exception:
        delete_file(temp_path)
        raise
