import asyncio
import os
import shutil
import subprocess
import threading
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from app.core.config import settings
from app.services.storage import delete_file

logger = logging.getLogger("savespeech.stt")


class STTException(Exception):
    """Exception khusus layanan STT dengan kode error dan pesan Bahasa Indonesia."""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def to_wav16k_mono(input_path: Path) -> Path:
    """Mengonversi file audio ke format WAV 16kHz mono 16-bit PCM menggunakan ffmpeg.
    Menghasilkan berkas temporer baru yang wajib dihapus di blok finally pemanggil.
    """
    output_path = settings.temp_dir_path / f"stt_{uuid.uuid4()}.wav"
    ffmpeg_cmd = shutil.which("ffmpeg")

    if not ffmpeg_cmd:
        # Fallback jika ffmpeg tidak terpasang (misal dalam unit test)
        logger.warning("ffmpeg tidak ditemukan di sistem, menggunakan berkas asli untuk pengujian.")
        shutil.copy(input_path, output_path)
        return output_path

    cmd = [
        ffmpeg_cmd,
        "-y",
        "-i", str(input_path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
        if res.returncode != 0:
            logger.error(f"ffmpeg conversion failed: {res.stderr}")
            delete_file(output_path)
            raise STTException("STT_FAILED", "Gagal mengonversi format audio ke 16kHz mono")
        return output_path
    except subprocess.TimeoutExpired:
        delete_file(output_path)
        raise STTException("STT_FAILED", "Konversi audio melebihi batas waktu (timeout)")
    except Exception as e:
        delete_file(output_path)
        if isinstance(e, STTException):
            raise
        raise STTException("STT_FAILED", f"Gagal memproses konversi audio: {str(e)}")


class WhisperModelSingleton:
    """Singleton pengelola model faster-whisper dengan pemuatan sekali saat startup (warmup)."""
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_model(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    from faster_whisper import WhisperModel
                    logger.info(
                        f"Memuat model Whisper '{settings.WHISPER_MODEL}' "
                        f"(device={settings.WHISPER_DEVICE}, compute={settings.WHISPER_COMPUTE})..."
                    )
                    cls._instance = WhisperModel(
                        settings.WHISPER_MODEL,
                        device=settings.WHISPER_DEVICE,
                        compute_type=settings.WHISPER_COMPUTE,
                    )
                    logger.info("Model Whisper berhasil dimuat ke memori.")
        return cls._instance

    @classmethod
    def set_instance(cls, mock_model):
        """Untuk keperluan mocking pada unit test."""
        with cls._lock:
            cls._instance = mock_model

    @classmethod
    def reset(cls):
        """Mereset instance model."""
        with cls._lock:
            cls._instance = None


def warmup_model() -> None:
    """Fungsi warmup untuk memuat model whisper sekali saat aplikasi start."""
    try:
        WhisperModelSingleton.get_model()
    except Exception as e:
        logger.warning(f"Warmup Whisper ditunda: {e}")


def _transcribe_sync(
    audio_path: Path,
    on_progress: Optional[Callable[[int], None]] = None,
    total_duration: float = 30.0,
) -> List[Dict[str, Any]]:
    """Proses transkripsi sinkron di dalam thread terpisah."""
    wav_16k_path: Optional[Path] = None
    try:
        # 1. Konversi ke 16kHz mono
        wav_16k_path = to_wav16k_mono(audio_path)

        # 2. Ambil model singleton
        model = WhisperModelSingleton.get_model()

        # 3. Transkripsikan dengan parameter PRD (language='id', vad_filter=True, beam_size=5)
        segments_gen, info = model.transcribe(
            str(wav_16k_path),
            language="id",
            vad_filter=True,
            beam_size=5,
        )

        audio_duration = info.duration if hasattr(info, "duration") and info.duration else total_duration
        if audio_duration <= 0:
            audio_duration = 1.0

        results = []
        for segment in segments_gen:
            text_clean = segment.text.strip()
            if text_clean:
                results.append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": text_clean,
                    "flagged": False,
                })
                # Petakan kemajuan segmen ke rentang 20% - 65%
                if on_progress:
                    ratio = min(1.0, segment.end / audio_duration)
                    progress_pct = 20 + int(ratio * 45)
                    on_progress(min(65, progress_pct))

        # 4. Validasi hasil transkrip
        if not results:
            raise STTException("NO_SPEECH", "Tidak ada percakapan terdeteksi pada audio")

        return results

    except STTException:
        raise
    except Exception as e:
        logger.exception("Kesalahan saat transkripsi:")
        raise STTException("STT_FAILED", f"Gagal melakukan Speech-to-Text: {str(e)}")
    finally:
        # Hapus berkas hasil konversi 16kHz
        if wav_16k_path:
            delete_file(wav_16k_path)


async def transcribe(
    audio_path: Path,
    on_progress: Optional[Callable[[int], None]] = None,
    total_duration: float = 30.0,
) -> List[Dict[str, Any]]:
    """Transkripsi asinkron yang berjalan di threadpool agar tidak memblokir event loop."""
    return await asyncio.to_thread(_transcribe_sync, audio_path, on_progress, total_duration)
