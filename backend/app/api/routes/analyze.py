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
from app.schemas.analysis import AnalyzeResponse

router = APIRouter(tags=["Analyze"])


async def run_pipeline_stub(job_id: str, file_path: Path) -> None:
    """Task asinkron latar belakang untuk memproses berkas audio.
    Blok finally menjamin berkas audio SELALU dihapus pada kondisi sukses maupun gagal.
    """
    try:
        # 1. Tahap uploading selesai -> transcribing (20-65%)
        job_manager.update_progress(job_id, "transcribing", 20)
        await asyncio.sleep(0.1)
        job_manager.update_progress(job_id, "transcribing", 45)
        await asyncio.sleep(0.1)

        # 2. Tahap analyzing (65-95%)
        job_manager.update_progress(job_id, "analyzing", 65)
        await asyncio.sleep(0.1)
        job_manager.update_progress(job_id, "analyzing", 85)
        await asyncio.sleep(0.1)

        # 3. Hasil dummy stub untuk Phase B4
        stub_result = {
            "jobId": job_id,
            "label": "NORMAL",
            "scamCategory": None,
            "riskScore": 15,
            "riskLevel": "Low",
            "explanation": "Panggilan normal tanpa indikasi penipuan (hasil simulasi Phase B4).",
            "indicators": [],
            "transcript": [
                {"start": 0.0, "end": 3.0, "text": "Halo selamat siang", "flagged": False}
            ],
            "overrideApplied": False,
        }
        job_manager.set_result(job_id, stub_result)

    except Exception as e:
        job_manager.mark_failed(job_id, f"Terjadi kesalahan pemrosesan audio: {str(e)}")
    finally:
        # SELALU hapus berkas audio dari direktori temporer pada blok finally
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
    # 1. Validasi ekstensi
    orig_name = file.filename or ""
    _, ext = os.path.splitext(orig_name.lower())

    # 2. Siapkan file tujuan dengan nama UUID acak
    temp_path = generate_temp_path(ext)

    try:
        # 3. Streaming validation & save
        await validate_and_save_upload(file, temp_path)

        # 4. Validasi durasi via ffprobe
        validate_audio_duration(temp_path)

        # 5. Buat job di memory
        job_id = job_manager.create_job(str(current_user.id))

        # 6. Jadwalkan pipeline di latar belakang
        background_tasks.add_task(run_pipeline_stub, job_id, temp_path)

        return AnalyzeResponse(job_id=job_id)

    except Exception:
        # Jika terjadi exception saat upload atau validasi awal, bersihkan file segera
        delete_file(temp_path)
        raise
