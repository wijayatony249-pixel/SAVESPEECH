import pytest
from ml.preprocessing import clean_text


def test_clean_text_lowercase_and_spacing():
    """Menguji konversi lowercase dan perapihan spasi berlebih."""
    raw = "  HALO   SELAMAT   SIANG  "
    assert clean_text(raw) == "halo selamat siang"


def test_clean_text_otp_normalization():
    """Menguji bahwa berbagai variasi penulisan OTP dinormalisasi menjadi token 'otp'."""
    assert "otp" in clean_text("kirimkan kode o-t-p bapak")
    assert "otp" in clean_text("masukkan kode o t p anda")
    assert "otp" in clean_text("berikan kode otp sms sekarang")
    assert "otp" in clean_text("one-time password jangan dibagikan")


def test_clean_text_numbers_to_token():
    """Menguji bahwa nomor dan nominal angka digantikan oleh token <num>."""
    raw = "Penarikan sebesar Rp 5.000.000 ke rekening 1234567890"
    cleaned = clean_text(raw)
    assert "<num>" in cleaned
    assert "5.000.000" not in cleaned
    assert "1234567890" not in cleaned


def test_clean_text_preserves_critical_stopwords():
    """KRUSIAL: Memastikan stopwords penting (jangan, segera, tidak) TIDAK dihapus."""
    raw = "Jangan pernah berikan kode ini! Segera batalkan jika tidak ingin diblokir."
    cleaned = clean_text(raw)
    assert "jangan" in cleaned
    assert "segera" in cleaned
    assert "tidak" in cleaned
    assert "diblokir" in cleaned


def test_clean_text_removes_fillers():
    """Menguji pembersihan kata-kata filler lisan (ehm, uhm, ahh)."""
    raw = "Ehm halo bapak, uhm tolong sebutkan kodenya ahh sekarang"
    cleaned = clean_text(raw)
    assert "ehm" not in cleaned
    assert "uhm" not in cleaned
    assert "ahh" not in cleaned
    assert "halo bapak" in cleaned


def test_clean_text_empty_and_none_input():
    """Menguji penanganan input kosong atau None."""
    assert clean_text("") == ""
    assert clean_text(None) == ""
