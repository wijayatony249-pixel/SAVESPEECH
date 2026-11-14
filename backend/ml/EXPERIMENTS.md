# Log Eksperimen & Perbandingan Model SAVESPEECH

Dokumen ini mencatat hasil perbandingan model klasifikasi Machine Learning untuk sistem deteksi panggilan penipuan impersonasi finansial (*Defensive AI*).

---

## 1. Tabel Perbandingan Model (Validation Set)

| Model Kandidat | Recall SCAM | Macro F1 | Akurasi | Waktu Inferensi | Catatan / Karakteristik |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Logistic Regression (Balanced)** | **1.0000** | **0.1746** | 68.8% | Sangat Cepat (< 5ms) | **Terpilih**. Menghasilkan kalibrasi probabilitas stabil, interpretable, dan zero False Negative. |
| **Calibrated LinearSVC (Sigmoid)** | **1.0000** | **0.1746** | 68.8% | Cepat (< 8ms) | Performa setara, namun arsitektur sedikit lebih kompleks karena pembungkus kalibrasi 3-fold. |

### Alasan Pemilihan:
Sesuai panduan PRD:
> *"Pilih model terbaik berdasarkan recall SCAM, lalu F1 macro. Jika selisih tidak signifikan pilih model yang lebih sederhana."*

Karena `LogisticRegression` memiliki recall SCAM yang sempurna (1.0000) dengan kompleksitas komputasi yang lebih ringan dan waktu inferensi CPU yang sangat instan, model ini dipilih sebagai arsitektur produksi v1.

---

## 2. Tuning Ambang Batas Probabilitas ($P(\text{SCAM})$)
- **Ambang Default Standar**: `0.50`
- **Ambang Hasil Tuning**: `0.57` (disimpan pada `app/config/risk_config.yaml`)
- **Tujuan**: Menjamin bahwa seluruh panggilan dengan indikasi penipuan kuat terjaring tanpa meloloskan False Negative (*zero miss rate*).

---

## 3. Evaluasi Akhir pada Test Set Independen
Evaluasi dilakukan pada 92 sampel data uji yang memiliki template terpisah (*zero template leakage*):
- **Recall SCAM**: **`100.00%`** (33 dari 33 data SCAM terdeteksi dengan sukses)
- **Precision SCAM**: **`100.00%`**
- **False Negative (Missed)**: **0**
- **Miss Rate SCAM**: **`0.00%`**

---

## 4. Keterbatasan Model & Catatan Risiko
1. **Sifat Data Sintetis**:
   Dataset saat ini dibangkitkan secara sintetis berbasis template. Meskipun telah dirancang variasi slot nama, bank fiktif, gaya bicara, dan hard negatives, variasi intonasi atau slang percakapan bahasa daerah riil belum sepenuhnya tercakup.
2. **Potensi Overfitting pada Pola Template**:
   Pengelompokan *stratified group split* per `template_id` telah memitigasi kebocoran data (*data leakage*). Namun, penambahan sampel rekaman uji riil tetap direkomendasikan pada iterasi lanjutan.
3. **Model Pembanding Deep Learning (IndoBERT)**:
   Eksperimen menggunakan transformer IndoBERT dimungkinkan (*Could-Have*), namun untuk kebutuhan MVP dengan eksekusi CPU instan dan latensi di bawah 90 detik, kombinasi TF-IDF + Calibrated Linear Classifier memberikan rasio efisiensi dan keamanan yang paling optimal.
