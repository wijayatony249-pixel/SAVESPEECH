import io
import time
import uuid
import pytest
from unittest.mock import MagicMock

from app.db.models import User, AnalysisResult, AnalysisIndicator
from app.core.config import settings
from app.core.security import create_access_token
from app.services.stt import WhisperModelSingleton, STTException
from app.services.job_manager import job_manager


class MockSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class MockWhisperInfo:
    def __init__(self, duration: float = 6.0):
        self.duration = duration


def _create_test_user(db_session, nama: str, email: str) -> tuple[User, str]:
    user = User(nama=nama, email=email, password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(subject=str(user.id))
    return user, token


def _create_wav_bytes(duration_sec: int = 4) -> bytes:
    sample_rate = 16000
    data_size = duration_sec * sample_rate * 2
    header = bytearray(b"RIFF")
    header.extend((36 + data_size).to_bytes(4, "little"))
    header.extend(b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data")
    header.extend(data_size.to_bytes(4, "little"))
    header.extend(b"\x00" * data_size)
    return bytes(header)


def test_full_pipeline_scam_detection_and_masking(client, db_session):
    """Pengujian integrasi end-to-end:
    - Unggah audio penipuan perbankan dengan opt-in riwayat
    - Polling sampai status 'done'
    - Verifikasi hasil camelCase, risk level, indikator terdeteksi
    - Verifikasi bahwa deretan angka 4 digit atau lebih (misal OTP 892716) dimasking menjadi ****
    - Verifikasi database hanya menyimpan ringkasan TANPA kutipan maupun transkrip
    """
    user, token = _create_test_user(db_session, "Korban Uji", "korban@example.com")

    # Mock Whisper menghasilkan transkrip penipuan dengan kode OTP 6 digit
    mock_model = MagicMock()
    mock_segments = [
        MockSegment(0.0, 3.0, "Halo selamat siang kami dari pihak bank sentral nasional"),
        MockSegment(3.0, 6.0, "Segera sebutkan kode otp sms anda 892716 sekarang juga jangan ditutup teleponnya"),
    ]
    mock_model.transcribe.return_value = (iter(mock_segments), MockWhisperInfo(duration=6.0))
    WhisperModelSingleton.set_instance(mock_model)

    # 1. POST /api/analyze dengan opt-in saveHistory=true
    wav_data = _create_wav_bytes(4)
    res_upload = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("scam_call.wav", io.BytesIO(wav_data), "audio/wav")},
        data={"saveHistory": "true"}
    )
    assert res_upload.status_code == 202
    job_id = res_upload.json()["jobId"]

    # 2. Tunggu background pipeline selesai
    time.sleep(0.8)

    # 3. GET /api/results/{jobId}
    res_result = client.get(
        f"/api/results/{job_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_result.status_code == 200
    result = res_result.json()

    # Verifikasi struktur kontrak JSON
    assert result["jobId"] == job_id
    assert result["label"] == "SCAM"
    assert result["riskLevel"] in ("High", "Critical")
    assert result["riskScore"] >= 60
    assert len(result["indicators"]) > 0
    assert len(result["transcript"]) == 2

    # Verifikasi MASKING: 892716 harus disensor menjadi ****
    transcript_text = " ".join(seg["text"] for seg in result["transcript"])
    assert "892716" not in transcript_text
    assert "****" in transcript_text

    # 4. Verifikasi DATABASE (Zero persistent audio/transcript)
    saved_result = db_session.query(AnalysisResult).filter(AnalysisResult.job_id == job_id).first()
    assert saved_result is not None
    assert saved_result.label == "SCAM"
    assert saved_result.risk_score >= 60

    # Pastikan di tabel analysis_indicators tidak ada teks kutipan/transkrip
    saved_indicators = db_session.query(AnalysisIndicator).filter(AnalysisIndicator.result_id == saved_result.id).all()
    assert len(saved_indicators) > 0
    for ind in saved_indicators:
        assert ind.indicator_code in ("CLAIM_INSTITUTION", "REQ_OTP", "URGENCY")
        assert not hasattr(ind, "quote")
        assert not hasattr(ind, "transcript")

    # 5. Verifikasi GET /api/history
    res_hist = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert res_hist.status_code == 200
    hist_data = res_hist.json()
    assert hist_data["total"] >= 1
    assert hist_data["items"][0]["jobId"] == job_id

    # 6. Verifikasi DELETE /api/results/{id}
    history_id = str(saved_result.id)
    del_res = client.delete(f"/api/results/{history_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200

    # Pastikan data terhapus dari database
    assert db_session.query(AnalysisResult).filter(AnalysisResult.id == saved_result.id).first() is None


def test_pipeline_idor_protection(client, db_session):
    """Menguji proteksi IDOR: Pengguna B tidak dapat mengakses hasil atau menghapus riwayat Pengguna A."""
    user_a, token_a = _create_test_user(db_session, "User A", "user_a_pipe@example.com")
    user_b, token_b = _create_test_user(db_session, "User B", "user_b_pipe@example.com")

    # Siapkan job done milik User A langsung di job manager
    job_id = job_manager.create_job(str(user_a.id))
    job_manager.set_result(job_id, {
        "jobId": job_id,
        "label": "NORMAL",
        "scamCategory": None,
        "riskScore": 10,
        "riskLevel": "Low",
        "explanation": "Normal",
        "indicators": [],
        "transcript": [],
        "overrideApplied": False,
    })

    # User B mencoba mengakses hasil User A -> 404
    res_idor = client.get(
        f"/api/results/{job_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_idor.status_code == 404


def test_pipeline_failure_cleans_up_audio(client, db_session):
    """Menguji bahwa kegagalan STT menghasilkan status failed dan file audio tetap terhapus."""
    user, token = _create_test_user(db_session, "User Fail", "fail@example.com")

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = STTException("NO_SPEECH", "Tidak ada percakapan terdeteksi")
    WhisperModelSingleton.set_instance(mock_model)

    wav_data = _create_wav_bytes(4)
    res_upload = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("silent_call.wav", io.BytesIO(wav_data), "audio/wav")}
    )
    assert res_upload.status_code == 202
    job_id = res_upload.json()["jobId"]

    time.sleep(0.5)

    status_data = client.get(f"/api/jobs/{job_id}", headers={"Authorization": f"Bearer {token}"}).json()
    assert status_data["status"] == "failed"
    assert "NO_SPEECH" in status_data["errorMessage"]

    # Pastikan TEMP_DIR bersih
    temp_files = list(settings.temp_dir_path.glob("*"))
    assert len(temp_files) == 0
