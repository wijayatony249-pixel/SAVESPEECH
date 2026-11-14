import time
import uuid
import threading
from typing import Dict, Any, Optional
from fastapi import HTTPException, status


class JobManager:
    """Manajer job in-memory dengan thread-safe lock dan TTL 15 menit."""

    def __init__(self, ttl_seconds: int = 900):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def _cleanup_expired_jobs(self) -> None:
        """Membersihkan job yang telah melebihi batas waktu TTL."""
        now = time.time()
        expired_ids = [
            jid for jid, job in self._jobs.items()
            if (now - job["created_at"]) > self._ttl_seconds
        ]
        for jid in expired_ids:
            del self._jobs[jid]

    def create_job(self, user_id: str) -> str:
        """Membuat job baru untuk pengguna.
        Tolak dengan 429 jika pengguna sudah memiliki job aktif (uploading, transcribing, analyzing).
        """
        user_id_str = str(user_id)
        with self._lock:
            self._cleanup_expired_jobs()

            # Periksa apakah user memiliki job aktif
            for job in self._jobs.values():
                if job["user_id"] == user_id_str and job["status"] in ("uploading", "transcribing", "analyzing"):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Anda masih memiliki proses analisis audio yang sedang berjalan. Harap tunggu hingga selesai.",
                    )

            job_id = str(uuid.uuid4())
            self._jobs[job_id] = {
                "job_id": job_id,
                "user_id": user_id_str,
                "status": "uploading",
                "progress": 0,
                "error_message": None,
                "result": None,
                "created_at": time.time(),
            }
            return job_id

    def update_progress(
        self,
        job_id: str,
        status_name: str,
        progress: int,
        error_message: Optional[str] = None
    ) -> None:
        """Memperbarui status dan persentase progres job."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status_name
                self._jobs[job_id]["progress"] = progress
                if error_message:
                    self._jobs[job_id]["error_message"] = error_message

    def set_result(self, job_id: str, result_data: Dict[str, Any]) -> None:
        """Menyimpan hasil analisis lengkap ke dalam job (in-memory) dan menandai status 'done'."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["result"] = result_data
                self._jobs[job_id]["status"] = "done"
                self._jobs[job_id]["progress"] = 100

    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Menandai job sebagai 'failed' beserta pesan errornya."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error_message"] = error_message

    def get_job(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """Mengambil data job. Jika job tidak ada atau milik orang lain,
        selalu kembalikan 404 untuk mencegah enumerasi job (IDOR mitigation).
        """
        user_id_str = str(user_id)
        with self._lock:
            self._cleanup_expired_jobs()
            job = self._jobs.get(job_id)
            if not job or job["user_id"] != user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Job analisis tidak ditemukan",
                )
            return dict(job)

    def clear(self) -> None:
        """Mereset semua data job (berguna untuk pengujian)."""
        with self._lock:
            self._jobs.clear()


job_manager = JobManager()
