import asyncio
import os
import time
import uuid
import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("savespeech.storage")


def generate_temp_path(ext: str) -> Path:
    """Menghasilkan path penyimpanan berkas temporer acak dengan nama UUID."""
    clean_ext = ext if ext.startswith(".") else f".{ext}"
    filename = f"{uuid.uuid4()}{clean_ext}"
    dest_path = settings.temp_dir_path / filename

    # Set izin berkas 600 di sistem operasi Unix/POSIX jika memungkinkan
    if os.name != "nt":
        try:
            dest_path.touch(mode=0o600, exist_ok=True)
        except Exception:
            pass

    return dest_path


def delete_file(file_path: Optional[Path]) -> bool:
    """Menghapus berkas audio sementara secara aman."""
    if not file_path:
        return False
    try:
        p = Path(file_path)
        if p.exists():
            p.unlink(missing_ok=True)
            logger.debug(f"File sementara berhasil dihapus: {p.name}")
            return True
    except Exception as e:
        logger.warning(f"Gagal menghapus file sementara {file_path}: {e}")
    return False


def cleanup_expired_files(max_age_seconds: int = 900) -> int:
    """Membersihkan file audio sementara di TEMP_DIR yang umurnya melebihi batas (default 15 menit)."""
    temp_dir = settings.temp_dir_path
    now = time.time()
    deleted_count = 0

    if not temp_dir.exists():
        return 0

    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            try:
                file_age = now - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink(missing_ok=True)
                    deleted_count += 1
            except Exception as e:
                logger.warning(f"Error saat membersihkan file {file_path.name}: {e}")

    if deleted_count > 0:
        logger.info(f"Sweeper membersihkan {deleted_count} file audio kedaluwarsa dari {temp_dir}.")
    return deleted_count


async def periodic_storage_sweeper(interval_seconds: int = 60, max_age_seconds: int = 900) -> None:
    """Background task periodik untuk membersihkan berkas yang tertinggal."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            cleanup_expired_files(max_age_seconds=max_age_seconds)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Terjadi kesalahan pada periodic sweeper: {e}")
