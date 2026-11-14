import pytest
from app.services.risk_engine import compute_risk
from app.services.indicators import detect_indicators


def test_risk_score_calculation_example_from_prd():
    """Menguji contoh persis dari PRD:
    P(SCAM) = 0.93
    Indikator: bank 15 + OTP 30 + urgency 10 + transfer 25 + blokir 15 (Total = 95)
    Skor: round(0.6 * 93 + 0.4 * 95) = round(55.8 + 38) = 94 (Critical)
    """
    indicators = [
        {"code": "CLAIM_INSTITUTION", "label": "Mengaku Bank", "weight": 15},
        {"code": "REQ_OTP", "label": "Permintaan OTP", "weight": 30},
        {"code": "URGENCY", "label": "Urgency", "weight": 10},
        {"code": "TRANSFER_INSTRUCTION", "label": "Instruksi Transfer", "weight": 25},
        {"code": "BLOCK_THREAT", "label": "Ancaman Blokir", "weight": 15},
    ]
    res = compute_risk(p_scam=0.93, indicators=indicators, base_label="SCAM")

    assert res["riskScore"] == 94
    assert res["riskLevel"] == "Critical"
    assert res["label"] == "SCAM"
    assert "94" not in res["explanation"]  # Penjelasan tidak kaku dan tidak menuduh
    assert len(res["explanation"]) > 20


def test_override_rule_low_pscam():
    """Menguji aturan override:
    Klaim lembaga keuangan + (OTP atau PIN) memaksa minimal level High
    dan jika label ML sebelumnya NORMAL, maka diubah menjadi SUSPICIOUS dengan overrideApplied=True.
    """
    indicators = [
        {"code": "CLAIM_INSTITUTION", "label": "Klaim Bank", "weight": 15},
        {"code": "REQ_OTP", "label": "Permintaan OTP", "weight": 30},
    ]
    # P(SCAM) sangat rendah (0.05)
    res = compute_risk(p_scam=0.05, indicators=indicators, base_label="NORMAL")

    # Tanpa override: 0.6 * 5 + 0.4 * 45 = 3 + 18 = 21 (Low)
    # Dengan override: dipaksa minimal High (skor minimal 60) dan label SUSPICIOUS
    assert res["riskLevel"] == "High"
    assert res["riskScore"] >= 60
    assert res["label"] == "SUSPICIOUS"
    assert res["overrideApplied"] is True
    assert "Aturan pengamanan ketat diterapkan" in res["explanation"]


def test_normal_transcript_results_in_low():
    """Menguji bahwa transkrip normal menghasilkan tingkat risiko Low tanpa indikator."""
    res = compute_risk(p_scam=0.05, indicators=[], base_label="NORMAL")
    assert res["riskScore"] <= 29
    assert res["riskLevel"] == "Low"
    assert res["label"] == "NORMAL"
    assert res["overrideApplied"] is False
    assert "rendah" in res["explanation"].lower()


def test_indicator_quote_max_15_words():
    """Menguji bahwa kutipan bukti yang diekstrak oleh detektor indikator tidak melebihi 15 kata."""
    long_segment_text = (
        "Selamat siang bapak kami dari pihak bank sentral nasional indonesia ingin memberitahukan "
        "bahwa ada transaksi ilegal sangat besar segera sebutkan enam digit kode otp sms anda sekarang "
        "juga jangan ditutup teleponnya karena sistem kami akan memproses pembatalan secepatnya terima kasih"
    )
    segments = [{"start": 0.0, "end": 10.0, "text": long_segment_text, "flagged": False}]

    detected = detect_indicators(segments)
    assert len(detected) > 0

    for item in detected:
        quote = item["quote"]
        words = quote.split()
        assert len(words) <= 15, f"Kutipan melebihi 15 kata ({len(words)} kata): '{quote}'"


def test_custom_yaml_weights_effect():
    """Menguji bahwa konfigurasi bobot khusus mengubah kalkulasi skor risiko secara dinamis."""
    custom_cfg = {
        "coefficients": {"ml": 0.5, "indicators": 0.5},
        "thresholds": {"levels": {"low": 0, "medium": 40, "high": 70, "critical": 90}},
    }
    indicators = [{"code": "REQ_OTP", "label": "OTP", "weight": 40}]
    # 0.5 * (0.8 * 100) + 0.5 * 40 = 40 + 20 = 60
    res = compute_risk(p_scam=0.80, indicators=indicators, base_label="SCAM", config=custom_cfg)
    assert res["riskScore"] == 60
    assert res["riskLevel"] == "Medium"
