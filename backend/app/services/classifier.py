import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional
import joblib

from ml.preprocessing import clean_text

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent.parent / "ml" / "artifacts" / "v1"
CLASSIFIER_PATH = ARTIFACTS_DIR / "classifier.joblib"
CATEGORY_PATH = ARTIFACTS_DIR / "category_model.joblib"


class ClassifierService:
    """Service inferensi model klasifikasi penipuan (singleton)."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._classifier_data = None
        self._category_data = None
        self._load_artifacts()

    def _load_artifacts(self):
        if CLASSIFIER_PATH.exists():
            self._classifier_data = joblib.load(CLASSIFIER_PATH)
        if CATEGORY_PATH.exists():
            self._category_data = joblib.load(CATEGORY_PATH)

    @classmethod
    def get_instance(cls) -> "ClassifierService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def predict(self, text: str) -> Dict[str, Any]:
        """Melakukan inferensi teks transkrip percakapan."""
        if not self._classifier_data:
            self._load_artifacts()

        if not self._classifier_data:
            # Fallback jika model belum dilatih
            return {
                "label": "NORMAL",
                "probabilities": {"NORMAL": 0.9, "SUSPICIOUS": 0.05, "SCAM": 0.05},
                "pScam": 0.05,
                "scamCategory": None,
            }

        vec = self._classifier_data["vectorizer"]
        model = self._classifier_data["model"]
        threshold = self._classifier_data.get("scam_threshold", 0.50)
        classes = list(model.classes_)

        cleaned = clean_text(text)
        X = vec.transform([cleaned])
        probs = model.predict_proba(X)[0]

        prob_dict = {cls_name: round(float(p), 4) for cls_name, p in zip(classes, probs)}
        scam_idx = classes.index("SCAM")
        p_scam = float(probs[scam_idx])

        # Tentukan label berdasarkan ambang batas pScam
        if p_scam >= threshold:
            label = "SCAM"
        elif p_scam >= (threshold * 0.5):
            label = "SUSPICIOUS"
        else:
            label = "NORMAL"

        # Tentukan scamCategory jika label SCAM atau SUSPICIOUS
        scam_category = None
        if label == "SCAM" and self._category_data:
            cat_vec = self._category_data["vectorizer"]
            cat_model = self._category_data["model"]
            X_cat = cat_vec.transform([cleaned])
            scam_category = cat_model.predict(X_cat)[0]

        return {
            "label": label,
            "probabilities": prob_dict,
            "pScam": round(p_scam, 4),
            "scamCategory": scam_category,
        }


classifier_service = ClassifierService.get_instance()
