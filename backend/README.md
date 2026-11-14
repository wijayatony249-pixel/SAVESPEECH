# SAVESPEECH Backend

API dan Pipeline AI untuk Sistem Deteksi Panggilan Penipuan Impersonasi Finansial (Bank, E-Wallet, Customer Service).
Dikembangkan menggunakan FastAPI, faster-whisper, scikit-learn, dan PostgreSQL.

---

## Prasyarat
- Python 3.10 atau 3.11
- FFmpeg (untuk ekstraksi dan konversi audio)
- PostgreSQL 15+

---

## Instalasi & Menjalankan Lokal

### 1. Buat Virtual Environment
```bash
# Masuk ke folder backend
cd backend

# Buat virtual environment
python -m venv venv

# Aktivasi virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate
```

### 2. Instal Dependencies
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Environment
Salin template konfigurasi:
```bash
cp .env.example .env
```
Sesuaikan nilai `DATABASE_URL` dan parameter lainnya di dalam berkas `.env`.

### 4. Menjalankan Server Development
```bash
uvicorn app.main:app --reload --port 8000
```
Server akan berjalan di `http://localhost:8000`.
- Dokumentasi Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

---

## Menjalankan Pengujian (Testing)
```bash
pytest -v
```
