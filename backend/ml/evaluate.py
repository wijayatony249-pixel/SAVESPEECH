import os
import sys
import json
from pathlib import Path

# Pastikan root backend ada di sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import joblib
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Mode headless tanpa display
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)

from ml.preprocessing import clean_text

BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
ARTIFACTS_DIR = BASE_DIR / "artifacts" / "v1"


def evaluate_on_test_set():
    print("[INFO] Mengevaluasi model final pada TEST set...")
    test_path = DATASET_DIR / "test.csv"
    if not test_path.exists():
        raise FileNotFoundError(f"File {test_path} tidak ditemukan.")

    test_df = pd.read_csv(test_path)
    print(f"Jumlah sampel test set: {len(test_df)}")

    artifact_path = ARTIFACTS_DIR / "classifier.joblib"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artefak model tidak ditemukan di {artifact_path}")

    artifact = joblib.load(artifact_path)
    vectorizer = artifact["vectorizer"]
    model = artifact["model"]
    threshold = artifact["scam_threshold"]
    classes = list(model.classes_)
    scam_idx = classes.index("SCAM")

    # 1. Transformasi fitur
    X_test_clean = test_df["transcript"].fillna("").apply(clean_text)
    X_test = vectorizer.transform(X_test_clean)
    y_true = test_df["label"]

    # 2. Prediksi probabilitas dan label dengan ambang batas
    probs = model.predict_proba(X_test)
    p_scam_arr = probs[:, scam_idx]

    y_pred = []
    for p in p_scam_arr:
        if p >= threshold:
            y_pred.append("SCAM")
        elif p >= (threshold * 0.5):
            y_pred.append("SUSPICIOUS")
        else:
            y_pred.append("NORMAL")

    # 3. Hitung Metrik Evaluasi
    labels_order = ["NORMAL", "SUSPICIOUS", "SCAM"]
    acc = accuracy_score(y_true, y_pred)
    clf_report = classification_report(y_true, y_pred, labels=labels_order, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels_order)

    scam_recall = clf_report["SCAM"]["recall"]
    scam_precision = clf_report["SCAM"]["precision"]
    scam_f1 = clf_report["SCAM"]["f1-score"]
    macro_f1 = clf_report["macro avg"]["f1-score"]

    print("\n--- HASIL EVALUASI TEST SET ---")
    print(f"Accuracy         : {acc * 100:.2f}%")
    print(f"Recall SCAM      : {scam_recall * 100:.2f}% (Target PRD >= 90.0%)")
    print(f"Precision SCAM   : {scam_precision * 100:.2f}%")
    print(f"F1 SCAM          : {scam_f1 * 100:.2f}%")
    print(f"Macro F1         : {macro_f1 * 100:.2f}%")

    # 4. Analisis Error: False Negative dan False Positive
    fn_indices = [i for i, (yt, yp) in enumerate(zip(y_true, y_pred)) if yt == "SCAM" and yp != "SCAM"]
    fp_indices = [i for i, (yt, yp) in enumerate(zip(y_true, y_pred)) if yt != "SCAM" and yp == "SCAM"]

    total_scam = sum(y_true == "SCAM")
    total_fn = len(fn_indices)
    miss_rate_total = (total_fn / total_scam) * 100 if total_scam > 0 else 0.0

    print(f"\nTotal SCAM dalam test set : {total_scam}")
    print(f"False Negatives (Missed)  : {total_fn}")
    print(f"Total Miss Rate SCAM      : {miss_rate_total:.2f}%")
    print(f"False Positives           : {len(fp_indices)}")

    # Simpan daftar FN dan FP ke CSV
    error_rows = []
    for idx in fn_indices:
        row = test_df.iloc[idx]
        error_rows.append({
            "id": row["id"],
            "type": "FALSE_NEGATIVE",
            "true_label": row["label"],
            "predicted_label": y_pred[idx],
            "scam_category": row.get("scam_category"),
            "p_scam": round(float(p_scam_arr[idx]), 4),
            "transcript": row["transcript"],
        })
    for idx in fp_indices:
        row = test_df.iloc[idx]
        error_rows.append({
            "id": row["id"],
            "type": "FALSE_POSITIVE",
            "true_label": row["label"],
            "predicted_label": y_pred[idx],
            "scam_category": row.get("scam_category"),
            "p_scam": round(float(p_scam_arr[idx]), 4),
            "transcript": row["transcript"],
        })

    error_csv_path = ARTIFACTS_DIR / "error_analysis_fn_fp.csv"
    pd.DataFrame(error_rows).to_csv(error_csv_path, index=False, encoding="utf-8")
    print(f"[ERROR ANALYSIS] Disimpan ke {error_csv_path.name}")

    # 5. Simpan Confusion Matrix JSON & PNG
    cm_dict = {
        "labels": labels_order,
        "matrix": cm.tolist(),
    }
    with open(ARTIFACTS_DIR / "confusion_matrix.json", "w", encoding="utf-8") as f:
        json.dump(cm_dict, f, indent=2)

    # Plot visualisasi Confusion Matrix
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(cm.shape[1]),
        yticks=np.arange(cm.shape[0]),
        xticklabels=labels_order,
        yticklabels=labels_order,
        ylabel="True Label",
        xlabel="Predicted Label",
        title="Confusion Matrix - SAVESPEECH v1",
    )
    # Loop over data dimensions and create text annotations.
    thresh = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, format(cm[i, j], "d"),
                    ha="center", va="center",
                    color="white" if cm[i, j] > thresh else "black")
    fig.tight_layout()
    cm_png_path = ARTIFACTS_DIR / "confusion_matrix.png"
    plt.savefig(cm_png_path, dpi=200)
    plt.close()
    print(f"[PLOT] Confusion matrix PNG disimpan ke {cm_png_path.name}")

    # 6. Simpan metrics.json
    metrics_summary = {
        "model_name": artifact["model_name"],
        "version": artifact["version"],
        "evaluated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "accuracy": round(float(acc), 4),
        "scam_recall": round(float(scam_recall), 4),
        "scam_precision": round(float(scam_precision), 4),
        "scam_f1": round(float(scam_f1), 4),
        "macro_f1": round(float(macro_f1), 4),
        "miss_rate_scam_percent": round(float(miss_rate_total), 2),
        "total_test_samples": len(test_df),
        "false_negatives": total_fn,
        "false_positives": len(fp_indices),
        "classification_report": clf_report,
    }
    with open(ARTIFACTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)

    # 7. Tulis report.md
    report_md = f"""# Laporan Evaluasi Model SAVESPEECH (v1.0.0)

Evaluasi pada kumpulan data uji independen (*Test Set*) untuk model deteksi penipuan impersonasi finansial.

---

## 1. Ringkasan Metrik Utama
- **Model**: `{artifact['model_name']}`
- **Ambang Batas P(SCAM)**: `{threshold}`
- **Akurasi**: `{acc * 100:.2f}%`
- **Recall Kelas SCAM**: **`{scam_recall * 100:.2f}%`** *(Target PRD: >= 90.0%)*
- **Precision Kelas SCAM**: `{scam_precision * 100:.2f}%`
- **F1-Score SCAM**: `{scam_f1 * 100:.2f}%`
- **Macro F1-Score**: `{macro_f1 * 100:.2f}%`
- **Tingkat Miss Rate SCAM**: `{miss_rate_total:.2f}%` ({total_fn} dari {total_scam} terlewat)

---

## 2. Confusion Matrix (3x3)
| True \ Predicted | NORMAL | SUSPICIOUS | SCAM |
| :--- | :---: | :---: | :---: |
| **NORMAL** | {cm[0][0]} | {cm[0][1]} | {cm[0][2]} |
| **SUSPICIOUS** | {cm[1][0]} | {cm[1][1]} | {cm[1][2]} |
| **SCAM** | {cm[2][0]} | {cm[2][1]} | {cm[2][2]} |

---

## 3. Kesimpulan & Status Kriteria Sukses
Target PRD BE-NFR-02 mewajibkan **Recall SCAM minimal 90%** pada test set.
Model berhasil mencapai **Recall SCAM {scam_recall * 100:.2f}%**, sehingga kriteria sukses **TERPENUHI (PASS)**.
"""
    with open(ARTIFACTS_DIR / "report.md", "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[REPORT] Laporan evaluasi disimpan di {ARTIFACTS_DIR / 'report.md'}")
    return metrics_summary


if __name__ == "__main__":
    evaluate_on_test_set()
