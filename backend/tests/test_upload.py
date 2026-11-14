import io
import time
import pytest
from unittest.mock import MagicMock
from app.db.models import User
from app.core.config import settings
from app.core.security import create_access_token
from app.services.stt import WhisperModelSingleton


class MockSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class MockWhisperInfo:
    def __init__(self, duration: float = 4.0):
        self.duration = duration


@pytest.fixture(autouse=True)
def mock_whisper_for_upload():
    mock_model = MagicMock()
    mock_segments = [MockSegment(0.0, 3.0, "Halo selamat siang")]
    mock_model.transcribe.return_value = (iter(mock_segments), MockWhisperInfo())
    WhisperModelSingleton.set_instance(mock_model)
    yield
    WhisperModelSingleton.reset()


def _create_test_user(db_session, nama: str, email: str) -> tuple[User, str]:
    user = User(nama=nama, email=email, password_hash="hash", role="user")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    token = create_access_token(subject=str(user.id))
    return user, token


def _create_minimal_wav_bytes(duration_sec: int = 4) -> bytes:
    """Membuat struktur binary header berkas WAV RIFF valid."""
    sample_rate = 16000
    num_channels = 1
    bits_per_sample = 16
    data_size = duration_sec * sample_rate * num_channels * (bits_per_sample // 8)
    file_size = 36 + data_size

    header = bytearray()
    header.extend(b"RIFF")
    header.extend(file_size.to_bytes(4, "little"))
    header.extend(b"WAVE")
    header.extend(b"fmt ")
    header.extend((16).to_bytes(4, "little"))  # Subchunk1Size
    header.extend((1).to_bytes(2, "little"))   # PCM
    header.extend(num_channels.to_bytes(2, "little"))
    header.extend(sample_rate.to_bytes(4, "little"))
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    header.extend(byte_rate.to_bytes(4, "little"))
    block_align = num_channels * (bits_per_sample // 8)
    header.extend(block_align.to_bytes(2, "little"))
    header.extend(bits_per_sample.to_bytes(2, "little"))
    header.extend(b"data")
    header.extend(data_size.to_bytes(4, "little"))
    header.extend(b"\x00" * data_size)
    return bytes(header)


def test_upload_without_token_returns_401(client):
    """Menguji bahwa upload tanpa autentikasi ditolak (401)."""
    wav_content = _create_minimal_wav_bytes(4)
    res = client.post(
        "/api/analyze",
        files={"file": ("test.wav", io.BytesIO(wav_content), "audio/wav")}
    )
    assert res.status_code == 401


def test_fake_exe_rejected(client, db_session):
    """Menguji bahwa file berekstensi .mp3 tetapi berisi header biner .exe (MZ) ditolak (400)."""
    _, token = _create_test_user(db_session, "User A", "usera@example.com")
    fake_exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 100

    res = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malicious.mp3", io.BytesIO(fake_exe_content), "audio/mpeg")}
    )
    assert res.status_code == 400
    assert "magic bytes" in res.json()["error"]["message"].lower()


def test_invalid_extension_rejected(client, db_session):
    """Menguji penolakan ekstensi yang tidak diizinkan (.txt)."""
    _, token = _create_test_user(db_session, "User B", "userb@example.com")
    res = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("script.txt", io.BytesIO(b"halo dunia"), "text/plain")}
    )
    assert res.status_code == 400
    assert "tidak didukung" in res.json()["error"]["message"].lower()


def test_oversize_file_rejected(client, db_session, monkeypatch):
    """Menguji penolakan file melebihi batas ukuran MAX_UPLOAD_MB tanpa crash."""
    _, token = _create_test_user(db_session, "User C", "userc@example.com")
    # Turunkan batas menjadi 1 MB untuk test cepat
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    wav_header = _create_minimal_wav_bytes(1)
    oversized_data = wav_header + (b"\x00" * (2 * 1024 * 1024))  # 2 MB

    res = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("large.wav", io.BytesIO(oversized_data), "audio/wav")}
    )
    assert res.status_code == 400
    assert "melebihi batas maksimal" in res.json()["error"]["message"].lower()


def test_valid_upload_status_and_idor_protection(client, db_session):
    """Menguji upload berkas valid, polling status job, dan proteksi IDOR antar-user."""
    user_a, token_a = _create_test_user(db_session, "User A", "user_a@example.com")
    user_b, token_b = _create_test_user(db_session, "User B", "user_b@example.com")

    wav_content = _create_minimal_wav_bytes(4)

    # 1. User A upload audio
    res = client.post(
        "/api/analyze",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("rekaman.wav", io.BytesIO(wav_content), "audio/wav")}
    )
    assert res.status_code == 202
    data = res.json()
    assert "jobId" in data
    job_id = data["jobId"]

    # 2. User B mencoba mengakses status pekerjaan User A -> Wajib 404 (IDOR mitigation)
    idor_res = client.get(
        f"/api/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert idor_res.status_code == 404

    # 3. User A memantau status pekerjaannya sendiri
    status_res = client.get(
        f"/api/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["jobId"] == job_id
    assert status_data["status"] in ("uploading", "transcribing", "analyzing", "done")

    # 4. Tunggu background task selesai
    time.sleep(0.5)
    final_status = client.get(
        f"/api/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    ).json()
    assert final_status["status"] == "done"
    assert final_status["progress"] == 100

    # 5. Verifikasi bahwa TEMP_DIR kosong setelah background task selesai
    temp_files = list(settings.temp_dir_path.glob("*"))
    assert len(temp_files) == 0, f"Ditemukan berkas tersisa di TEMP_DIR: {[f.name for f in temp_files]}"
