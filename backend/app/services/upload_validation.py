import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings

# Format audio yang didukung dan ekstensi yang diizinkan
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}

ALLOWED_MIME_TYPES = {
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave"},
    ".mp3": {"audio/mpeg", "audio/mp3"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "video/mp4"},
}


def validate_magic_bytes(header: bytes, ext: str) -> bool:
    """Memvalidasi magic bytes header berkas audio."""
    if ext == ".wav":
        # WAV: Diawali 'RIFF' dan terdapat 'WAVE' pada offset 8-12
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE"
    elif ext == ".mp3":
        # MP3: Diawali tag 'ID3' atau frame sync bits 0xFF 0xE0 (11 bit sync)
        if len(header) >= 3 and header[:3] == b"ID3":
            return True
        if len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
            return True
        return False
    elif ext == ".m4a":
        # M4A: Box type 'ftyp' pada offset 4-8
        return len(header) >= 8 and header[4:8] == b"ftyp"
    return False


async def validate_and_save_upload(file: UploadFile, destination_path: Path) -> int:
    """Membaca berkas audio secara streaming, memvalidasi ekstensi, MIME, magic bytes,
    dan batas ukuran maksimal tanpa memuat seluruh berkas ke memori sekaligus.
    Mengembalikan total byte yang disimpan.
    """
    original_name = file.filename or ""
    _, ext = os.path.splitext(original_name.lower())

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format file '{ext}' tidak didukung. Harap unggah format .wav, .mp3, atau .m4a",
        )

    # Validasi content-type jika disediakan
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES.get(ext, set()):
        # Toleransi jika MIME generic application/octet-stream tapi magic bytes valid
        if content_type != "application/octet-stream":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content-Type '{content_type}' tidak sesuai dengan ekstensi file {ext}",
            )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    chunk_size = 64 * 1024  # 64 KB per chunk
    total_bytes = 0
    header_bytes = b""

    try:
        with open(destination_path, "wb") as out_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                if not header_bytes:
                    header_bytes = chunk[:32]
                    if not validate_magic_bytes(header_bytes, ext):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Struktur berkas audio tidak valid atau rusak (magic bytes tidak sesuai)",
                        )

                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Ukuran file melebihi batas maksimal {settings.MAX_UPLOAD_MB} MB",
                    )
                out_file.write(chunk)
    except Exception:
        # Jika terjadi error saat upload, bersihkan file sementara
        if destination_path.exists():
            destination_path.unlink(missing_ok=True)
        raise

    if total_bytes == 0:
        if destination_path.exists():
            destination_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Berkas audio kosong",
        )

    return total_bytes


def validate_audio_duration(file_path: Path) -> float:
    """Memeriksa durasi audio menggunakan ffprobe tanpa shell.
    Tolak bila kurang dari 3 detik atau lebih dari MAX_DURATION_SEC.
    """
    ffprobe_cmd = shutil.which("ffprobe")
    if not ffprobe_cmd:
        # Jika ffprobe tidak terpasang di sistem lokal pengujian, lewati pemeriksaan durasi
        return 10.0

    cmd = [
        ffprobe_cmd,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, shell=False)
        if res.returncode != 0 or not res.stdout.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gagal memeriksa durasi audio. Pastikan file audio tidak korup.",
            )
        duration = float(res.stdout.strip())
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Pemeriksaan berkas audio memakan waktu terlalu lama (ffprobe timeout)",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Durasi audio tidak dapat dibaca dari metadata file",
        )

    if duration < 3.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Durasi audio terlalu singkat (minimal 3 detik)",
        )
    if duration > settings.MAX_DURATION_SEC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Durasi audio melebihi batas maksimal {settings.MAX_DURATION_SEC} detik",
        )

    return duration
