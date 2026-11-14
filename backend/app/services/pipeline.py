import uuid
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.db.session import SessionLocal
from app.db.models import AnalysisResult, AnalysisIndicator
from app.services.storage import delete_file
from app.services.job_manager import job_manager
from app.services.stt import transcribe, STTException
from app.services.classifier import classifier_service
from app.services.indicators import detect_indicators
from app.services.risk_engine import compute_risk
from app.services.masking import mask_segments, mask_indicators

logger = logging.getLogger("savespeech.pipeline")


async def run_pipeline(
    job_id: str,
    file_path: Path,
    user_id: str,
    save_history: bool = False,
    duration: float = 30.0,
) -> None:
    """Orkestrasi Pipeline Analisis Audio End-to-End:
    Audio -> STT -> Preprocessing -> Classifier ML -> Indikator -> Risk Engine -> Masking -> In-Memory Result (+ Opt-in DB).
    """
    try:
        # 1. Tahap Speech-to-Text (faster-whisper)
        job_manager.update_progress(job_id, "transcribing", 20)

        def on_stt_progress(pct: int):
            job_manager.update_progress(job_id, "transcribing", pct)

        segments = await transcribe(file_path, on_progress=on_stt_progress, total_duration=duration)

        # 2. Tahap Analisis: Preprocessing & ML Classifier
        job_manager.update_progress(job_id, "analyzing", 65)
        full_transcript = " ".join(seg["text"] for seg in segments)
        clf_result = classifier_service.predict(full_transcript)

        # 3. Deteksi Indikator Rule-Based
        job_manager.update_progress(job_id, "analyzing", 80)
        detected_indicators = detect_indicators(segments)

        # 4. Kalkulasi Risk Engine & Evaluasi Override
        risk_result = compute_risk(
            p_scam=clf_result["pScam"],
            indicators=detected_indicators,
            base_label=clf_result["label"],
        )

        # 5. Data Masking (Digit >= 4 disensor menjadi ****)
        masked_segments = mask_segments(segments)
        masked_indicators = mask_indicators(detected_indicators)

        # 6. Penyimpanan Riwayat Opt-in ke PostgreSQL (Hanya ringkasan tanpa audio/transkrip)
        if save_history:
            try:
                db = SessionLocal()
                expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                db_result = AnalysisResult(
                    id=uuid.uuid4(),
                    user_id=uuid.UUID(user_id),
                    job_id=job_id,
                    label=risk_result["label"],
                    scam_category=clf_result.get("scamCategory"),
                    risk_score=risk_result["riskScore"],
                    risk_level=risk_result["riskLevel"],
                    explanation=risk_result["explanation"],
                    expires_at=expires_at,
                )
                db.add(db_result)
                db.flush()

                # Simpan kode indikator dan bobot (TANPA kutipan/transkrip)
                for ind in detected_indicators:
                    db_ind = AnalysisIndicator(
                        result_id=db_result.id,
                        indicator_code=ind["code"],
                        weight=ind["weight"],
                    )
                    db.add(db_ind)

                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Gagal menyimpan riwayat opt-in: {e}")

        # 7. Simpan Hasil Lengkap ke In-Memory JobManager (TTL 15 Menit)
        result_payload = {
            "jobId": job_id,
            "label": risk_result["label"],
            "scamCategory": clf_result.get("scamCategory"),
            "riskScore": risk_result["riskScore"],
            "riskLevel": risk_result["riskLevel"],
            "explanation": risk_result["explanation"],
            "indicators": masked_indicators,
            "transcript": masked_segments,
            "overrideApplied": risk_result.get("overrideApplied", False),
        }
        job_manager.set_result(job_id, result_payload)

    except STTException as e:
        job_manager.mark_failed(job_id, f"[{e.code}] {e.message}")
    except Exception as e:
        logger.exception("Terjadi kesalahan pada pipeline:")
        job_manager.mark_failed(job_id, f"[PIPELINE_ERROR] {str(e)}")
    finally:
        # JAMINAN KEAMANAN: Berkas audio SELALU dihapus dari penyimpanan temporer
        delete_file(file_path)
