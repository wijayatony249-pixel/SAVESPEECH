import io
import time
import uuid
import logging
from unittest.mock import MagicMock
from collections import namedtuple

import pytest
from sqlalchemy import inspect

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import SensitiveDataFilter
from app.db.models import AnalysisResult, AnalysisIndicator, AuditLog, User, ModelVersion
from app.services.stt import WhisperModelSingleton
from app.services.job_manager import job_manager
from tests.conftest import TestingSessionLocal

MockSegment = namedtuple("MockSegment", ["start", "end", "text"])
MockWhisperInfo = namedtuple("MockWhisperInfo", ["duration"])


def _create_wav_bytes(duration_sec: int = 4, sample_rate: int = 16000) -> bytes:
    """Membuat payload WAV mono 16-bit valid untuk pengujian keamanan."""
    num_samples = duration_sec * sample_rate
    bytes_per_sample = 2
    data_size = num_samples * bytes_per_sample
    file_size = 36 + data_size

    header = bytearray(b"RIFF")
    header.extend(file_size.to_bytes(4, "little"))
    header.extend(b"WAVEfmt ")
    header.extend((16).to_bytes(4, "little"))  # Subchunk1Size
    header.extend((1).to_bytes(2, "little"))   # AudioFormat (PCM)
    header.extend((1).to_bytes(2, "little"))   # NumChannels (Mono)
    header.extend(sample_rate.to_bytes(4, "little"))  # SampleRate
    header.extend((sample_rate * bytes_per_sample).to_bytes(4, "little"))  # ByteRate
    header.extend((bytes_per_sample).to_bytes(2, "little"))  # BlockAlign
    header.extend((16).to_bytes(2, "little"))  # BitsPerSample
    header.extend(b"data")
    header.extend(data_size.to_bytes(4, "little"))
    return bytes(header) + b"\x00" * data_size


def _register_user(client, name="User Sec", email="user_sec@example.com", password="Password123!"):
    """Helper membuat user dan mengembalikan data login + token."""
    res = client.post("/api/auth/register", json={
        "nama": name,
        "email": email,
        "password": password
    })
    data = res.json()
    token = data["token"]
    user_id = data["user"]["id"]
    return user_id, token


def test_sec01_malicious_and_fake_file_types(client, db_session):
    """SEC-01: Verifikasi penolakan berkas mencurigakan / ekstensi palsu."""
    _, token = _register_user(client, "Sec User 1", "sec1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Berkas biner EXE yang diberi ekstensi .wav
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This is a fake windows binary"
    res1 = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("malware.wav", io.BytesIO(fake_exe), "audio/wav")}
    )
    assert res1.status_code == 400
    assert "magic bytes" in res1.json()["error"]["message"].lower()

    # 2. Skrip shell / text yang diberi ekstensi .mp3
    fake_sh = b"#!/bin/bash\nrm -rf / --no-preserve-root\n"
    res2 = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("exploit.mp3", io.BytesIO(fake_sh), "audio/mpeg")}
    )
    assert res2.status_code == 400
    assert "magic bytes" in res2.json()["error"]["message"].lower()

    # 3. Ekstensi terlarang langsung (.py)
    res3 = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("script.py", io.BytesIO(b"print('hack')"), "text/x-python")}
    )
    assert res3.status_code == 400
    assert "tidak didukung" in res3.json()["error"]["message"].lower()


def test_sec02_oversize_file_streaming_rejection(client, db_session, monkeypatch):
    """SEC-02: Verifikasi penolakan streaming berkas melebihi batas (HTTP 400)."""
    _, token = _register_user(client, "Sec User 2", "sec2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Turunkan batas ukuran untuk test cepat
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    wav_header = _create_wav_bytes(1)
    oversized_data = wav_header + (b"\x00" * (2 * 1024 * 1024))

    res = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("too_large.wav", io.BytesIO(oversized_data), "audio/wav")}
    )
    assert res.status_code == 400
    assert "melebihi batas maksimal" in res.json()["error"]["message"].lower()


def test_sec03_unauthorized_endpoints(client):
    """SEC-03: Verifikasi autentikasi wajib pada seluruh endpoint terproteksi (HTTP 401)."""
    protected_urls = [
        ("GET", "/api/auth/me"),
        ("POST", "/api/analyze"),
        ("GET", f"/api/jobs/{uuid.uuid4()}"),
        ("GET", f"/api/results/{uuid.uuid4()}"),
        ("GET", "/api/history"),
        ("DELETE", f"/api/results/{uuid.uuid4()}"),
    ]

    for method, url in protected_urls:
        # Tanpa header Authorization
        if method == "GET":
            res_no_auth = client.get(url)
        elif method == "POST":
            res_no_auth = client.post(url)
        elif method == "DELETE":
            res_no_auth = client.delete(url)
        assert res_no_auth.status_code == 401
        assert "error" in res_no_auth.json()

        # Dengan Bearer token palsu
        headers_bad = {"Authorization": "Bearer token_palsu_acakan_12345"}
        if method == "GET":
            res_bad = client.get(url, headers=headers_bad)
        elif method == "POST":
            res_bad = client.post(url, headers=headers_bad)
        elif method == "DELETE":
            res_bad = client.delete(url, headers=headers_bad)
        assert res_bad.status_code == 401
        assert "error" in res_bad.json()


def test_sec04_idor_isolation(client, db_session):
    """SEC-04: Mitigasi IDOR (Insecure Direct Object Reference).
    User B tidak boleh mengakses pekerjaan, hasil analisis, atau riwayat milik User A.
    """
    user_a_id, token_a = _register_user(client, "User A", "user_a@example.com")
    user_b_id, token_b = _register_user(client, "User B", "user_b@example.com")

    # Siapkan mock Whisper
    mock_model = MagicMock()
    mock_segments = [MockSegment(0.0, 3.0, "Panggilan biasa")]
    mock_model.transcribe.return_value = (iter(mock_segments), MockWhisperInfo(duration=3.0))
    WhisperModelSingleton.set_instance(mock_model)

    # User A mengunggah berkas
    wav_data = _create_wav_bytes(4)
    res_upload_a = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("sample.wav", io.BytesIO(wav_data), "audio/wav")},
        data={"saveHistory": "true"}
    )
    assert res_upload_a.status_code == 202
    job_id_a = res_upload_a.json()["jobId"]

    # Beri jeda untuk background processing selesai
    time.sleep(0.8)

    # 1. User B mencoba mengakses status pekerjaan User A -> HTTP 404 (IDOR dicegah)
    res_job_b = client.get(f"/api/jobs/{job_id_a}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_job_b.status_code == 404

    # 2. User B mencoba membaca hasil pekerjaan User A -> HTTP 404
    res_res_b = client.get(f"/api/results/{job_id_a}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_res_b.status_code == 404

    # 3. User B mencoba membaca daftar riwayat User A -> User B hanya melihat riwayat miliknya (0 entri)
    res_hist_b = client.get("/api/history", headers={"Authorization": f"Bearer {token_b}"})
    assert res_hist_b.status_code == 200
    assert len(res_hist_b.json()["items"]) == 0

    # User A membaca riwayat miliknya -> ada 1 entri
    res_hist_a = client.get("/api/history", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hist_a.status_code == 200
    assert len(res_hist_a.json()["items"]) == 1
    item_a_id = res_hist_a.json()["items"][0]["id"]

    # 4. User B mencoba menghapus item riwayat milik User A -> HTTP 404
    res_del_b = client.delete(f"/api/results/{item_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_del_b.status_code == 404


def test_sec05_rate_limiting_login_and_register(client):
    """SEC-05: Verifikasi pembatasan laju permintaan (Rate Limiting)."""
    limiter.reset()

    # 1. Login rate limit: 5 per menit per IP
    for _ in range(5):
        res = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "WrongPassword1!"})
        assert res.status_code == 401

    # Percobaan ke-6 harus ditolak dengan HTTP 429
    res_login_block = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "WrongPassword1!"})
    assert res_login_block.status_code == 429
    assert res_login_block.json()["error"]["code"] == 429


def test_sec06_single_active_job_concurrency(client):
    """SEC-06: Verifikasi aturan satu job aktif per user (HTTP 429 ACTIVE_JOB_EXISTS)."""
    user_id, token = _register_user(client, "Concurrent User", "concurrent@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Buat job aktif buatan di JobManager
    job_id = job_manager.create_job(user_id=user_id)
    job_manager.update_progress(job_id, "transcribing", 30)

    # Pengguna mencoba mengunggah audio lain saat job masih aktif
    wav_data = _create_wav_bytes(4)
    res = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("another.wav", io.BytesIO(wav_data), "audio/wav")}
    )
    assert res.status_code == 429
    assert "proses analisis audio yang sedang berjalan" in res.json()["error"]["message"].lower()


def test_sec07_zero_persistent_audio_guarantee(client, db_session):
    """SEC-07: Jaminan Zero Persistent Audio.
    Direktori temporer SELALU kosong setelah analisis selesai, baik berhasil maupun gagal.
    """
    _, token = _register_user(client, "Zero Audio User", "zero_audio@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Pastikan direktori temporer awal kosong
    temp_files_before = [f for f in settings.temp_dir_path.iterdir() if f.is_file()]
    assert len(temp_files_before) == 0

    # Kasus A: Analisis Berhasil
    mock_model = MagicMock()
    mock_model.transcribe.return_value = (iter([MockSegment(0.0, 3.0, "Uji audio")]), MockWhisperInfo(duration=3.0))
    WhisperModelSingleton.set_instance(mock_model)

    wav_data = _create_wav_bytes(4)
    res = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("test_clean.wav", io.BytesIO(wav_data), "audio/wav")}
    )
    assert res.status_code == 202
    time.sleep(0.8)

    # Verifikasi direktori bersih setelah pemrosesan sukses
    temp_files_after_success = [f for f in settings.temp_dir_path.iterdir() if f.is_file()]
    assert len(temp_files_after_success) == 0

    # Kasus B: Analisis Gagal (Simulasi exception STT)
    mock_failing_model = MagicMock()
    mock_failing_model.transcribe.side_effect = RuntimeError("Simulasi kerusakan decoder audio!")
    WhisperModelSingleton.set_instance(mock_failing_model)

    res_fail = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("test_fail.wav", io.BytesIO(wav_data), "audio/wav")}
    )
    assert res_fail.status_code == 202
    time.sleep(0.8)

    # Verifikasi direktori tetap bersih walau pipeline mengalami crash/exception
    temp_files_after_failure = [f for f in settings.temp_dir_path.iterdir() if f.is_file()]
    assert len(temp_files_after_failure) == 0


def test_sec08_zero_transcript_in_db():
    """SEC-08: Jaminan Zero Transcript di Basis Data PostgreSQL.
    Memverifikasi skema tabel sama sekali tidak memiliki kolom penyimpanan transkrip atau audio.
    """
    inspector = inspect(AnalysisResult)
    analysis_columns = [c.name for c in inspector.columns]

    # Kolom terlarang yang dilarang ada di database
    forbidden_columns = [
        "transcript",
        "audio",
        "audio_path",
        "audio_file",
        "raw_text",
        "cleaned_text",
        "text",
        "quote",
        "content"
    ]

    for col in forbidden_columns:
        assert col not in analysis_columns, f"Kolom sensitif '{col}' ditemukan pada AnalysisResult!"

    # Periksa AnalysisIndicator
    ind_inspector = inspect(AnalysisIndicator)
    ind_columns = [c.name for c in ind_inspector.columns]
    for col in ["quote", "text", "transcript", "matched_text", "audio"]:
        assert col not in ind_columns, f"Kolom sensitif '{col}' ditemukan pada AnalysisIndicator!"


def test_sec09_audit_log_and_app_log_redaction(client, db_session):
    """SEC-09: Verifikasi audit log dan logger tidak membocorkan data sensitif."""
    secret_pass = "RahasiaSangatKuat99!"
    _, token = _register_user(client, "Audited User", "audit@example.com", password=secret_pass)

    logs = db_session.query(AuditLog).all()
    assert len(logs) > 0

    for l in logs:
        # Audit log hanya menyimpan action, status, dan ip_hash
        assert len(l.ip_hash) == 64
        assert l.action in ["register", "login_success", "login_failed"]

    # Verifikasi filter redaksi log aplikasi (SensitiveDataFilter)
    log_filter = SensitiveDataFilter()
    dummy_record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Login dengan password=RahasiaSuper123 dan token=eyJh... serta otp 928172",
        args=(),
        exc_info=None
    )
    log_filter.filter(dummy_record)
    assert "RahasiaSuper123" not in dummy_record.msg
    assert "[REDACTED]" in dummy_record.msg or "***" in dummy_record.msg


def test_sec10_security_headers(client):
    """SEC-10: Verifikasi keberadaan header HTTP pengerasan keamanan (Hardening)."""
    res = client.get("/api/health")
    headers = res.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert "max-age=31536000" in headers.get("strict-transport-security", "")
    assert "default-src 'self'" in headers.get("content-security-policy", "")
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_sec11_cors_protection(client):
    """SEC-11: Verifikasi pembatasan CORS (Cross-Origin Resource Sharing)."""
    # Origin yang diizinkan (Frontend Vite / React)
    res_allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # Origin tidak dikenal / penyerang
    res_blocked = client.options(
        "/api/health",
        headers={
            "Origin": "https://malicious-scam-site.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert res_blocked.headers.get("access-control-allow-origin") != "https://malicious-scam-site.com"


def test_sec12_credential_masking(client, db_session):
    """SEC-12: Verifikasi masking data kredensial (OTP, PIN, deret angka 4+ digit) menjadi ****."""
    _, token = _register_user(client, "Mask User", "mask@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    mock_model = MagicMock()
    mock_segments = [
        MockSegment(0.0, 3.0, "Mohon konfirmasi kode OTP SMS anda 948201 saat ini juga"),
        MockSegment(3.0, 6.0, "Dan masukkan PIN kartu debit 123456 pada tautan resmi")
    ]
    mock_model.transcribe.return_value = (iter(mock_segments), MockWhisperInfo(duration=6.0))
    WhisperModelSingleton.set_instance(mock_model)

    wav_data = _create_wav_bytes(4)
    res_upload = client.post(
        "/api/analyze",
        headers=headers,
        files={"file": ("credential_call.wav", io.BytesIO(wav_data), "audio/wav")},
        data={"saveHistory": "false"}
    )
    job_id = res_upload.json()["jobId"]
    time.sleep(0.8)

    res_result = client.get(f"/api/results/{job_id}", headers=headers)
    assert res_result.status_code == 200
    res_json = res_result.json()

    # Pastikan transkrip tidak mengandung angka OTP / PIN
    for seg in res_json["transcript"]:
        assert "948201" not in seg["text"]
        assert "123456" not in seg["text"]
        assert "****" in seg["text"]

    # Pastikan kutipan indikator juga termasking
    for ind in res_json["indicators"]:
        assert "948201" not in ind["quote"]
        assert "123456" not in ind["quote"]
