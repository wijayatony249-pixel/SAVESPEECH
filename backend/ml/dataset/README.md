# Dataset Sintetis SAVESPEECH

Direktori ini memuat modul generator dataset percakapan sintetis berbasis template dan alat pemecahan dataset (*stratified group split*) untuk sistem deteksi panggilan penipuan impersonasi finansial.

---

## 1. Aturan Keamanan & Privasi Data
- **100% Data Fiktif**: Seluruh nama individu, nama lembaga keuangan, nomor kartu, dan nomor telepon dibuat secara sintetis tanpa menggunakan data korban riil.
- **Hard Negatives**: Menyertakan notifikasi resmi bank yang secara eksplisit melarang pembagian OTP/PIN agar model tidak bias hanya terhadap penyebutan nama bank.

---

## 2. Cara Menjalankan Generator & Splitter

```powershell
# 1. Jalankan generator dataset mentah (~600 sampel)
python ml/dataset/generate_dataset.py

# 2. Lakukan stratified group split (70% train, 15% val, 15% test) tanpa kebocoran template
python ml/dataset/split_dataset.py
```

Berkas yang dihasilkan:
- `dataset_raw.csv`: Data mentah lengkap sebelum pemisahan.
- `train.csv`: Data latih untuk TF-IDF & classifier ML (~419 baris).
- `val.csv`: Data validasi untuk tuning ambang P(SCAM) (~93 baris).
- `test.csv`: Data uji untuk evaluasi akhir metrik Recall SCAM (~92 baris).

---

## 3. Catatan untuk Tim Proyek
Sesuai PRD, tim pengembang diwajibkan untuk:
1. Meninjau secara manual sampel percakapan yang dihasilkan pada `train.csv` dan `val.csv`.
2. Menambahkan variasi ungkapan bahasa lisan daerah atau variasi template baru jika ditemukan pola penipuan baru di lapangan.
