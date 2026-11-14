import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.core.config import settings
from app.services.stt import (
    to_wav16k_mono,
    _transcribe_sync,
    WhisperModelSingleton,
    STTException,
)


class MockSegment:
    def __init__(self, start: float, end: float, text: str):
        self.start = start
        self.end = end
        self.text = text


class MockWhisperInfo:
    def __init__(self, duration: float = 10.0):
        self.duration = duration


def _create_dummy_wav(path: Path) -> None:
    """Membuat berkas WAV dummy kecil untuk pengujian."""
    with open(path, "wb") as f:
        f.write(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00")


def test_stt_transcription_success(monkeypatch, tmp_path):
    """Menguji bahwa transkripsi menghasilkan segmen berstempel waktu dan memetakan progres ke 20-65%."""
    audio_file = tmp_path / "test_audio.wav"
    _create_dummy_wav(audio_file)

    mock_model = MagicMock()
    mock_segments = [
        MockSegment(0.0, 3.5, "Halo selamat siang dari bank"),
        MockSegment(3.5, 7.0, "Mohon konfirmasi kode OTP Anda"),
    ]
    mock_info = MockWhisperInfo(duration=7.0)
    mock_model.transcribe.return_value = (iter(mock_segments), mock_info)

    WhisperModelSingleton.set_instance(mock_model)

    progress_records = []
    def record_progress(pct: int):
        progress_records.append(pct)

    results = _transcribe_sync(audio_file, on_progress=record_progress, total_duration=7.0)

    assert len(results) == 2
    assert results[0]["start"] == 0.0
    assert results[0]["end"] == 3.5
    assert results[0]["text"] == "Halo selamat siang dari bank"
    assert results[1]["text"] == "Mohon konfirmasi kode OTP Anda"

    # Verifikasi progres dipetakan ke 20% - 65%
    assert len(progress_records) > 0
    assert min(progress_records) >= 20
    assert max(progress_records) <= 65


def test_stt_no_speech_error_on_silent_audio(tmp_path):
    """Menguji bahwa audio hening atau tanpa percakapan menghasilkan error kode NO_SPEECH."""
    audio_file = tmp_path / "silent.wav"
    _create_dummy_wav(audio_file)

    mock_model = MagicMock()
    # Tidak ada segmen atau segmen hanya spasi kosong
    mock_model.transcribe.return_value = (iter([]), MockWhisperInfo(duration=5.0))
    WhisperModelSingleton.set_instance(mock_model)

    with pytest.raises(STTException) as exc_info:
        _transcribe_sync(audio_file)

    assert exc_info.value.code == "NO_SPEECH"
    assert "tidak ada percakapan" in exc_info.value.message.lower()


def test_stt_cleans_up_temporary_conversion_file(tmp_path):
    """Menguji bahwa berkas .wav konversi sementara selalu dibersihkan di blok finally."""
    audio_file = tmp_path / "input.mp3"
    _create_dummy_wav(audio_file)

    # Catat isi folder temporer sebelum proses
    initial_files = set(settings.temp_dir_path.glob("*"))

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("Simulasi error tak terduga")
    WhisperModelSingleton.set_instance(mock_model)

    with pytest.raises(STTException) as exc_info:
        _transcribe_sync(audio_file)

    assert exc_info.value.code == "STT_FAILED"

    # Pastikan tidak ada file sementara stt_*.wav yang tertinggal
    current_files = set(settings.temp_dir_path.glob("*"))
    new_files = current_files - initial_files
    stt_temp_files = [f for f in new_files if f.name.startswith("stt_")]
    assert len(stt_temp_files) == 0, f"Ditemukan file sementara yang tidak terhapus: {stt_temp_files}"
