import asyncio
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
from app.services.stt import transcribe, STTException
from app.schemas.analysis import AnalyzeResponse

router = APIRouter(tags=["Analyze"])


async def run_analysis_pipeline(job_id: str, file_path: Path, duration: float = 30.0) -> None:
    """Pipeline pemrosesan audio asinkron.
    Blok finally menjamin berkas audio asli SELALU dihapus pada kondisi apa pun.
    """
    try:
        # 1. Tahap Speech-to-Text: transcribing (20-65%)
        job_manager.update_progress(job_id, "transcribing", 20)

        def on_stt_progress(pct: int):
            job_manager.update_progress(job_id, "transcribing", pct)

        segments = await transcribe(file_path, on_progress=on_stt_progress, total_duration=duration)

        # 2. Tahap Analisis ML & Risk Scoring: analyzing (65-95%)
        job_manager.update_progress(job_id, "analyzing", 65)
        await asyncio.sleep(0.1)
        job_manager.update_progress(job_id, "analyzing", 85)

        # 3. Hasil analisis (diintegrasikan penuh dengan model ML di Phase B7 & B8)
        stub_result = {
            "jobId": job_id,
            "label": "NORMAL",
            "scamCategory": None,
            "riskScore": 15,
            "riskLevel": "Low",
            "explanation": "Panggilan normal tanpa indikasi penipuan impersonasi.",
            "indicators": [],
            "transcript": segments,
            "overrideApplied": False,
        }
        job_manager.set_result(job_id, stub_result)

    except STTException as e:
        job_manager.mark_failed(job_id, f"[{e.code}] {e.message}")
    except Exception as e:
        job_manager.mark_failed(job_id, f"Terjadi kesalahan pemrosesan audio: {str(e)}")
    finally:
        # SELALU hapus berkas audio asli dari penyimpanan temporer
        delete_file(file_path)


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
        background_tasks.add_task(run_analysis_pipeline, job_id, temp_path, duration)

        return AnalyzeResponse(job_id=job_id)

    except Exception:
        delete_file(temp_path)
        raise
