import pytest
from pathlib import Path
import joblib

from ml.preprocessing import clean_text

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "v1" / "classifier.joblib"
CATEGORY_ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "v1" / "category_model.joblib"


def test_artifact_exists_and_loads():
    """Menguji bahwa artefak model ML hasil training v1 ada dan dapat dimuat ulang."""
    assert ARTIFACT_PATH.exists(), f"Artefak {ARTIFACT_PATH} tidak ditemukan!"
    data = joblib.load(ARTIFACT_PATH)
    assert "vectorizer" in data
    assert "model" in data
    assert "scam_threshold" in data
    assert "classes" in data
    assert "SCAM" in data["classes"]


def test_model_reproducible_prediction():
    """Menguji bahwa input yang sama menghasilkan prediksi dan probabilitas identik."""
    data = joblib.load(ARTIFACT_PATH)
    vec = data["vectorizer"]
    clf = data["model"]

    text = "halo bapak ini dari bank sentral mohon sebutkan kode otp sms anda sekarang"
    clean = clean_text(text)
    x = vec.transform([clean])

    prob1 = clf.predict_proba(x)[0]
    prob2 = clf.predict_proba(x)[0]

    assert (prob1 == prob2).all()
    scam_idx = list(clf.classes_).index("SCAM")
    assert prob1[scam_idx] > 0.5


def test_category_model_prediction():
    """Menguji bahwa model kategori memprediksi salah satu dari 5 kategori penipuan resmi."""
    assert CATEGORY_ARTIFACT_PATH.exists(), f"Artefak {CATEGORY_ARTIFACT_PATH} tidak ditemukan!"
    data = joblib.load(CATEGORY_ARTIFACT_PATH)
    vec = data["vectorizer"]
    clf = data["model"]
    allowed_categories = {
        "BANK_IMPERSONATION",
        "E_WALLET_IMPERSONATION",
        "OTP_SCAM",
        "TRANSFER_SCAM",
        "ACCOUNT_BLOCKING_SCAM",
    }

    text = "rekening anda terindikasi pencucian uang segera transfer ke rekening aman kepolisian"
    clean = clean_text(text)
    x = vec.transform([clean])
    predicted_category = clf.predict(x)[0]

    assert predicted_category in allowed_categories
