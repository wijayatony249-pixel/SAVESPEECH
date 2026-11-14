# SAVESPEECH Backend — Audio Scam Detection AI & API

Backend API dan Pipeline AI untuk deteksi panggilan penipuan berbasis peniruan identitas finansial (*financial impersonation scam call detection*) berbahasa Indonesia (Bank, E-Wallet, Kurir, Tagihan Pajak, Pemblokiran Rekening).

Proyek ini dibangun sebagai backend resmi pendamping frontend React SAVESPEECH dalam rangka pemenuhan Ujian Praktik Keamanan Informasi.

---

## 🏛️ Arsitektur Sistem & Alur Pipeline

```
  [ Frontend React ]
         │ (POST /api/analyze: file audio)
         ▼
  [ 1. Upload & Safe Validation ] ──> Magic Bytes, Whitelist Ext, Chunk Limit 25MB
         │
         ▼
  [ 2. Pre-processing Audio ]    ──> FFmpeg 16kHz Mono Converter
         │
         ▼
  [ 3. Speech-to-Text (STT) ]    ──> faster-whisper ('small', int8, CPU Singleton)
         │
         ▼
  [ 4. Pre-processing Teks ]     ──> Lowercase, Token Normalization (<num>, <otp>), Stopwords
         │
         ▼
  [ 5. Defensive AI Analysis ]
    ├─ ML Classifier (TF-IDF + Calibrated Classifier): P(SCAM), P(NORMAL), P(SUSPICIOUS)
    ├─ Indikator Penipuan (9 Rules + Regex): Bobot OTP(30), PIN(30), Transfer(25), dll.
    └─ Risk Engine: min(100, round(0.6 * P(SCAM)*100 + 0.4 * Score_ind))
         │
         ▼
  [ 6. Data Masking ]            ──> Masking Deret Angka >= 4 digit (OTP, PIN) menjadi ****
         │
         ▼
  [ 7. Secure Result Delivery ]
    ├─ In-Memory JobManager (TTL 15 Menit) -> GET /api/results/{jobId}
    ├─ ZERO Persistent Audio Storage -> Berkas audio LANGSUNG dihapus seketika
    └─ ZERO Transcript in DB -> Hanya metrik agregat disimpan jika saveHistory=true
```

---

## 🚀 Fitur Utama & Kepatuhan Keamanan (SEC-01 s/d SEC-12)

- **Defensive Multi-Layer AI**: Kombinasi Model Pembelajaran Mesin (TF-IDF n-gram + Logistic Regression terkalibrasi) dan 9 Indikator Aturan Penipuan berbasis leksikon.
- **Recall Target SCAM $\ge 90\%$**: Pada set pengujian independen 92 sampel, model mencapai **Recall SCAM 100%** tanpa False Negatives.
- **Rule Override**: Jika penelepon mengklaim lembaga resmi dan meminta kredensial rahasia (OTP/PIN), tingkat risiko otomatis diangkat ke minimal **High / Suspicious** meskipun probabilitas ML rendah.
- **Zero Persistent Audio**: Tidak ada rekaman suara pengguna yang tersimpan permanen di disk setelah pipeline selesai.
- **Zero Transcript di PostgreSQL**: Basis data PostgreSQL **sama sekali tidak memiliki kolom teks transkrip** demi privasi pengguna dan kepatuhan UU PDP No. 27 Tahun 2022.
- **IDOR Protection**: Validasi kepemilikan token JWT mencegah pengguna lain membaca status pekerjaan, hasil deteksi, atau riwayat milik orang lain.
- **Rate Limiting**: Slowapi in-memory/Redis limiter membatasi percobaan login (5/menit), registrasi (5/jam), dan unggah audio (10/menit).
- **Hardened HTTP Headers**: Menggunakan middleware `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Content-Security-Policy: default-src 'self'`.

---

## ⚡ Tolok Ukur Kecepatan Pemrosesan Audio (CPU Benchmark)

Diuji pada prosesor modern kelas konsumen (Intel Core i5 / AMD Ryzen 5, 4-8 Cores CPU, int8 quantization):

| Durasi Panggilan | Format Berkas | Waktu Transkripsi STT | Waktu Pipeline Analisis | Total Waktu Pemrosesan |
|---|---|---|---|---|
| **30 Detik** | WAV / MP3 | ~1.5 - 2.8 detik | ~0.1 detik | **~2 - 3 detik** |
| **1 Menit** | WAV / MP3 | ~3.2 - 5.5 detik | ~0.15 detik | **~3.5 - 6 detik** |
| **3 Menit** | WAV / MP3 | ~8.0 - 14.5 detik | ~0.25 detik | **~8.5 - 15 detik** |

---

## 🐳 Panduan Deployment Menggunakan Docker

Cara tercepat menjalankan SAVESPEECH Backend dan PostgreSQL adalah menggunakan Docker Compose:

### 1. Salin Konfigurasi Environment
```bash
cp .env.example .env
```
*(Pastikan mengganti `JWT_SECRET` dan `IP_HASH_SECRET` dengan string rahasia yang kuat).*

### 2. Jalankan Layanan dengan Docker Compose
```bash
docker compose up --build -d
```
Layanan akan berjalan pada:
- **Backend API**: `http://localhost:8000`
- **Swagger UI**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/api/health`
- **PostgreSQL**: Port `5432`

### 3. Matikan Layanan
```bash
docker compose down
```

---

## 💻 Panduan Instalasi Lokal (Tanpa Docker)

### 1. Prasyarat Sistem
- Python 3.10 atau 3.11
- FFmpeg (tersedia di PATH sistem)
- PostgreSQL 15+

### 2. Setup Virtual Environment & Dependensi
```bash
cd backend
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Migrasi Database & Buat Akun Admin
```bash
# Jalankan migrasi tabel
alembic upgrade head

# Buat admin awal
python scripts/create_admin.py --nama "Administrator" --email "admin@savespeech.id" --password "AdminSAVESPEECH2026!"
```

### 4. Jalankan Server Development
```bash
uvicorn app.main:app --reload --port 8000
```

---

## 🧪 Pengujian & Audit Keamanan

SAVESPEECH dilengkapi 57 pengujian otomatis yang mencakup fungsionalitas dan uji penetrasi keamanan:

```bash
# Menjalankan seluruh 57 automated tests:
pytest -v

# Menjalankan Audit Keamanan Statis (SAST Bandit):
bandit -r app -ll

# Menjalankan Audit Dependensi (pip-audit):
pip-audit -r requirements.txt
```

---

## 📖 Dokumentasi Lengkap
- **Panduan Integrasi Frontend**: [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md)
- **Katalog Endpoint API**: [API.md](API.md)
- **Kebijakan & Matriks Keamanan**: [SECURITY.md](SECURITY.md)
- **Laporan Evaluasi & Eksperimen ML**: [ml/EXPERIMENTS.md](ml/EXPERIMENTS.md)
