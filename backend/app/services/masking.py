import re
from typing import List, Dict, Any


def mask_sensitive_digits(text: str) -> str:
    """Memasking deretan digit numerik 4 angka atau lebih menjadi '****'.
    Termasuk nomor kartu, nomor rekening, nomor telepon, dan OTP angka.
    """
    if not text or not isinstance(text, str):
        return ""

    # Ganti pola nomor kartu berpemisah spasi/strip (e.g., 1234-5678-9012-3456)
    masked = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{2,4}[-\s]?\d{0,4}\b", "****", text)

    # Ganti deretan angka 4 digit atau lebih yang tersisa
    masked = re.sub(r"\b\d{4,}\b", "****", masked)

    return masked


def mask_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Memastikan teks di seluruh segmen transkrip dimasking sebelum dikirim ke frontend atau memori."""
    for seg in segments:
        if "text" in seg and isinstance(seg["text"], str):
            seg["text"] = mask_sensitive_digits(seg["text"])
    return segments


def mask_indicators(indicators: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Memastikan kutipan pada indikator yang terdeteksi dimasking."""
    for ind in indicators:
        if "quote" in ind and isinstance(ind["quote"], str):
            ind["quote"] = mask_sensitive_digits(ind["quote"])
    return indicators
