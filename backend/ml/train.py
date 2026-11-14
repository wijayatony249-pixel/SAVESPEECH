import os
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path

# Pastikan root backend ada di sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, recall_score, f1_score

from ml.preprocessing import clean_text

RANDOM_SEED = 42

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "v1"
CONFIG_DIR = BASE_DIR.parent / "app" / "config"


def train_models():
    print("[INFO] Memulai pelatihan model ML SAVESPEECH...")
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Muat dataset train dan val
    train_path = DATASET_DIR / "train.csv"
    val_path = DATASET_DIR / "val.csv"

    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError("train.csv atau val.csv tidak ditemukan. Jalankan generate & split dataset terlebih dahulu.")

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)

    print(f"Data latih: {len(train_df)}, Data validasi: {len(val_df)}")

    # 2. Preprocessing
    X_train_raw = train_df["transcript"].fillna("").apply(clean_text)
    y_train = train_df["label"]

    X_val_raw = val_df["transcript"].fillna("").apply(clean_text)
    y_val = val_df["label"]

    # 3. Ekstraksi Fitur TF-IDF
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        max_features=1500,
    )
    X_train = vectorizer.fit_transform(X_train_raw)
    X_val = vectorizer.transform(X_val_raw)

    # 4. Eksperimen Model: Logistic Regression vs Calibrated LinearSVC
    models = {
        "LogisticRegression": LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            C=1.0,
            random_state=RANDOM_SEED,
        ),
        "CalibratedLinearSVC": CalibratedClassifierCV(
            estimator=LinearSVC(class_weight="balanced", C=1.0, random_state=RANDOM_SEED),
            method="sigmoid",
            cv=3,
        ),
    }

    best_model_name = None
    best_model = None
    best_scam_recall = -1.0
    best_f1_macro = -1.0
    val_reports = {}

    for name, model in models.items():
        model.fit(X_train, y_train)
        preds = model.predict(X_val)

        report = classification_report(y_val, preds, output_dict=True, zero_division=0)
        val_reports[name] = report
        scam_rec = report["SCAM"]["recall"]
        macro_f1 = report["macro avg"]["f1-score"]

        print(f"[{name}] Val Recall SCAM: {scam_rec:.4f} | Macro F1: {macro_f1:.4f}")

        # Prioritas: Recall SCAM tertinggi, lalu F1 Macro
        if scam_rec > best_scam_recall or (scam_rec == best_scam_recall and macro_f1 > best_f1_macro):
            best_scam_recall = scam_rec
            best_f1_macro = macro_f1
            best_model_name = name
            best_model = model

    print(f"\n[HASIL PEMILIHAN] Model terbaik terpilih: {best_model_name} (Recall SCAM={best_scam_recall:.4f})")

    # 5. Tuning Ambang P(SCAM) pada Validation Set
    classes = list(best_model.classes_)
    scam_idx = classes.index("SCAM")
    probs_val = best_model.predict_proba(X_val)
    p_scam_val = probs_val[:, scam_idx]

    # Cari ambang probabilitas optimal untuk mencapai Recall SCAM >= 0.90 dengan presisi tertinggi
    thresholds = np.linspace(0.20, 0.60, 41)
    best_threshold = 0.50
    target_recall = 0.90
    found_threshold = False

    for th in reversed(thresholds):
        # Jika probabilitas SCAM >= th, tandai sebagai SCAM
        binary_preds = ["SCAM" if p >= th else ("SUSPICIOUS" if p >= (th * 0.6) else "NORMAL") for p in p_scam_val]
        rep = classification_report(y_val, binary_preds, output_dict=True, zero_division=0)
        rec = rep["SCAM"]["recall"]
        if rec >= target_recall:
            best_threshold = round(float(th), 2)
            found_threshold = True
            break

    if not found_threshold:
        best_threshold = 0.35  # Ambang konservatif defensif

    print(f"[TUNING] Ambang batas P(SCAM) disetel ke: {best_threshold}")

    # Simpan ambang ke risk_config.yaml
    risk_config_path = CONFIG_DIR / "risk_config.yaml"
    risk_config_data = {
        "version": "1.0",
        "weights": {
            "ml_probability": 0.6,
            "indicators": 0.4,
        },
        "thresholds": {
            "scam_probability": best_threshold,
            "levels": {
                "low": 0,
                "medium": 30,
                "high": 60,
                "critical": 85,
            },
        },
        "override": {
            "require_institution_and_credential": True,
            "forced_min_level": "High",
        },
    }
    with open(risk_config_path, "w", encoding="utf-8") as f:
        yaml.dump(risk_config_data, f, default_flow_style=False)
    print(f"[CONFIG] Disimpan ke {risk_config_path.name}")

    # 6. Latih Model Kategori Scam Terpisah (5 Kelas)
    print("\n[INFO] Melatih model klasifikasi kategori penipuan (5 kelas)...")
    scam_train_df = train_df[train_df["label"] == "SCAM"].copy()
    X_cat_raw = scam_train_df["transcript"].fillna("").apply(clean_text)
    y_cat = scam_train_df["scam_category"]

    cat_vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    X_cat = cat_vectorizer.fit_transform(X_cat_raw)

    cat_model = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=RANDOM_SEED)
    cat_model.fit(X_cat, y_cat)

    # 7. Simpan Artefak Model ke ml/artifacts/v1/
    artifact_main = {
        "model_name": best_model_name,
        "version": "v1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vectorizer": vectorizer,
        "model": best_model,
        "classes": classes,
        "scam_threshold": best_threshold,
        "parameters": {"ngram_range": (1, 2), "max_features": 1500},
    }
    artifact_path = ARTIFACTS_DIR / "classifier.joblib"
    joblib.dump(artifact_main, artifact_path)

    artifact_cat = {
        "version": "v1.0.0",
        "vectorizer": cat_vectorizer,
        "model": cat_model,
        "classes": list(cat_model.classes_),
    }
    joblib.dump(artifact_cat, ARTIFACTS_DIR / "category_model.joblib")

    print(f"[SUCCESS] Artefak model berhasil disimpan di {ARTIFACTS_DIR}")
    return best_model_name, best_threshold


if __name__ == "__main__":
    train_models()
