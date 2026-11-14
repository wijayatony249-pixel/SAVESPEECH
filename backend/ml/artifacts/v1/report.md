# Laporan Evaluasi Model SAVESPEECH (v1.0.0)

Evaluasi pada kumpulan data uji independen (*Test Set*) untuk model deteksi penipuan impersonasi finansial.

---

## 1. Ringkasan Metrik Utama
- **Model**: `LogisticRegression`
- **Ambang Batas P(SCAM)**: `0.57`
- **Akurasi**: `61.96%`
- **Recall Kelas SCAM**: **`100.00%`** *(Target PRD: >= 90.0%)*
- **Precision Kelas SCAM**: `100.00%`
- **F1-Score SCAM**: `100.00%`
- **Macro F1-Score**: `58.09%`
- **Tingkat Miss Rate SCAM**: `0.00%` (0 dari 33 terlewat)

---

## 2. Confusion Matrix (3x3)
| True \ Predicted | NORMAL | SUSPICIOUS | SCAM |
| :--- | :---: | :---: | :---: |
| **NORMAL** | 5 | 35 | 0 |
| **SUSPICIOUS** | 0 | 19 | 0 |
| **SCAM** | 0 | 0 | 33 |

---

## 3. Kesimpulan & Status Kriteria Sukses
Target PRD BE-NFR-02 mewajibkan **Recall SCAM minimal 90%** pada test set.
Model berhasil mencapai **Recall SCAM 100.00%**, sehingga kriteria sukses **TERPENUHI (PASS)**.
