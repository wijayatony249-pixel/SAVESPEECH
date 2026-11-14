import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "risk_config.yaml"


def load_risk_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Memuat konfigurasi bobot dan ambang risiko dari risk_config.yaml."""
    target_path = path or CONFIG_PATH
    if not target_path.exists():
        return {
            "coefficients": {"ml": 0.6, "indicators": 0.4},
            "thresholds": {"levels": {"low": 0, "medium": 30, "high": 60, "critical": 85}},
        }
    with open(target_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def calculate_risk_level(score: int, levels_config: Dict[str, int]) -> str:
    """Menentukan kategori level risiko berdasarkan skor 0-100."""
    critical_th = levels_config.get("critical", 85)
    high_th = levels_config.get("high", 60)
    medium_th = levels_config.get("medium", 30)

    if score >= critical_th:
        return "Critical"
    elif score >= high_th:
        return "High"
    elif score >= medium_th:
        return "Medium"
    else:
        return "Low"


def generate_explanation(
    indicators: List[Dict[str, Any]],
    risk_level: str,
    override_applied: bool = False
) -> str:
    """Menghasilkan penjelasan berbasis template Bahasa Indonesia (2-4 kalimat).
    Nada penjelasan objektif, informatif, dan tidak menuduh secara sepihak.
    """
    if not indicators or risk_level == "Low":
        return (
            "Percakapan ini dinilai memiliki tingkat risiko rendah dan tidak ditemukan indikator penipuan yang mencurigakan. "
            "Hasil ini merupakan indikasi risiko pendukung keputusan dan bukan jaminan mutlak. "
            "Tetap selalu berhati-hati dan jaga kerahasiaan informasi akun finansial Anda."
        )

    # Ambil hingga 3 indikator berbobot tertinggi
    sorted_inds = sorted(indicators, key=lambda x: x.get("weight", 0), reverse=True)
    top_labels = [ind["label"] for ind in sorted_inds[:3]]
    ind_str = ", ".join(top_labels)

    sentence1 = f"Panggilan ini terindikasi memiliki potensi risiko pada tingkat {risk_level} karena terdeteksi adanya {ind_str}."
    sentence2 = "Hasil analisis ini merupakan indikasi risiko pendukung keputusan dan bukan vonis akhir atas identitas penelepon."
    sentence3 = "Untuk perlindungan Anda, jangan pernah membagikan kode OTP, nomor PIN, atau mentransfer dana ke rekening yang tidak dikenal. Selalu verifikasi langsung ke kanal resmi lembaga terkait."

    if override_applied:
        sentence1 += " Aturan pengamanan ketat diterapkan karena terdapat klaim representasi lembaga yang disertai permintaan kredensial rahasia."

    return f"{sentence1} {sentence2} {sentence3}"


def compute_risk(
    p_scam: float,
    indicators: List[Dict[str, Any]],
    base_label: str = "NORMAL",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Menghitung Risk Score gabungan ML + Indikator, menentukan Risk Level,
    dan mengevaluasi aturan Override.
    
    Formula:
    Risk Score = min(100, round(0.6 * P(SCAM) * 100 + 0.4 * SkorIndikator))
    """
    cfg = config or load_risk_config()
    coeffs = cfg.get("coefficients", {"ml": 0.6, "indicators": 0.4})
    c_ml = coeffs.get("ml", 0.6)
    c_ind = coeffs.get("indicators", 0.4)
    levels_cfg = cfg.get("thresholds", {}).get("levels", {"low": 0, "medium": 30, "high": 60, "critical": 85})

    # 1. Total bobot indikator
    indicator_score = sum(ind.get("weight", 0) for ind in indicators)

    # 2. Perhitungan Skor Risiko terkalibrasi
    raw_score = (c_ml * p_scam * 100) + (c_ind * indicator_score)
    risk_score = min(100, round(raw_score))

    # 3. Kategori Level Risiko
    risk_level = calculate_risk_level(risk_score, levels_cfg)

    # 4. Aturan Override Keamanan
    # Klaim lembaga keuangan DAN (OTP atau PIN) -> minimal High
    ind_codes = {ind.get("code") for ind in indicators}
    has_institution_claim = "CLAIM_INSTITUTION" in ind_codes
    has_credential_req = ("REQ_OTP" in ind_codes) or ("REQ_CREDENTIAL" in ind_codes)

    override_applied = False
    final_label = base_label

    if has_institution_claim and has_credential_req:
        if risk_level in ("Low", "Medium"):
            risk_level = "High"
            risk_score = max(risk_score, 60)
            override_applied = True
        if base_label == "NORMAL":
            final_label = "SUSPICIOUS"
            override_applied = True

    # 5. Generator Penjelasan
    explanation = generate_explanation(indicators, risk_level, override_applied)

    return {
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "label": final_label,
        "overrideApplied": override_applied,
        "explanation": explanation,
    }
