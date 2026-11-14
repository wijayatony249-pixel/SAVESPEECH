# SAVESPEECH Backend — API Reference Manual

Dokumen ini memuat spesifikasi lengkap seluruh RESTful API yang disediakan oleh SAVESPEECH Backend.
- **Base URL**: `http://localhost:8000/api`
- **Format Data**: JSON (`application/json`) dan `multipart/form-data` (untuk upload audio)
- **Konvensi JSON Key**: camelCase
- **Format Pesan Kesalahan**:
  ```json
  {
    "error": {
      "code": 400,
      "message": "Pesan kesalahan dalam Bahasa Indonesia"
    }
  }
  ```

---

## Daftar Endpoint

| Modul | Method | Endpoint | Deskripsi | Autentikasi |
|---|---|---|---|---|
| **Health** | `GET` | `/api/health` | Status kesehatan servis backend & database | Publik |
| **Auth** | `POST` | `/api/auth/register` | Pendaftaran akun baru | Publik |
| **Auth** | `POST` | `/api/auth/login` | Masuk dan memperoleh JWT Bearer token | Publik |
| **Auth** | `GET` | `/api/auth/me` | Membaca profil pengguna aktif | Bearer Token |
| **Analysis**| `POST` | `/api/analyze` | Mengunggah rekaman audio panggilan untuk dianalisis | Bearer Token |
| **Jobs** | `GET` | `/api/jobs/{jobId}` | Polling status kemajuan analisis in-memory | Bearer Token |
| **Results** | `GET` | `/api/results/{jobId}` | Mengambil laporan lengkap hasil deteksi | Bearer Token |
| **History** | `GET` | `/api/history` | Mengambil daftar riwayat ringkasan analisis opt-in | Bearer Token |
| **Results** | `DELETE`| `/api/results/{id}` | Menghapus entri riwayat analisis dari basis data | Bearer Token |

---

## 1. Health Check

### `GET /api/health`
Mengembalikan status ketersediaan backend, versi aplikasi, dan konektivitas database.

**Respons (200 OK):**
```json
{
  "status": "healthy",
  "appEnv": "development",
  "version": "1.0.0",
  "database": "connected"
}
```

---

## 2. Autentikasi

### `POST /api/auth/register`
Mendaftarkan akun baru. Password wajib memuat minimal 8 karakter, 1 huruf besar, 1 huruf kecil, dan 1 angka.

**Request Body (`application/json`):**
```json
{
  "nama": "Budi Santoso",
  "email": "budi.santoso@example.com",
  "password": "Password123!"
}
```

**Respons Sukses (201 Created):**
```json
{
  "user": {
    "id": "e7b0c954-41d3-4f9a-a309-8b291a27e7f1",
    "nama": "Budi Santoso",
    "email": "budi.santoso@example.com"
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Respons Error (409 Conflict):**
```json
{
  "error": {
    "code": 409,
    "message": "Email sudah terdaftar"
  }
}
```

---

### `POST /api/auth/login`
Autentikasi dengan email dan password. Dibatasi maksimal 5 percobaan per menit per IP.

**Request Body (`application/json`):**
```json
{
  "email": "budi.santoso@example.com",
  "password": "Password123!"
}
```

**Respons Sukses (200 OK):**
```json
{
  "user": {
    "id": "e7b0c954-41d3-4f9a-a309-8b291a27e7f1",
    "nama": "Budi Santoso",
    "email": "budi.santoso@example.com"
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Respons Error (401 Unauthorized / Mitigasi Enumerasi):**
```json
{
  "error": {
    "code": 401,
    "message": "Email atau kata sandi salah"
  }
}
```

---

### `GET /api/auth/me`
Membaca informasi profil pengguna berdasarkan JWT token yang dikirimkan.

**Headers:**
```
Authorization: Bearer <token>
```

**Respons Sukses (200 OK):**
```json
{
  "id": "e7b0c954-41d3-4f9a-a309-8b291a27e7f1",
  "nama": "Budi Santoso",
  "email": "budi.santoso@example.com"
}
```

---

## 3. Pipeline Analisis Audio

### `POST /api/analyze`
Mengunggah berkas rekaman suara (.wav, .mp3, .m4a) untuk diproses oleh pipeline AI.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: Berkas biner audio (maks 25 MB, durasi 3 - 600 detik).
- `saveHistory`: (Opsional, boolean string: `"true"` atau `"false"`, default `"false"`).

**Respons Sukses (202 Accepted):**
```json
{
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "uploading",
  "message": "Berkas audio berhasil diunggah dan proses analisis dimulai"
}
```

**Respons Error:**
- `400 Bad Request`: `{"error": {"code": 400, "message": "Format berkas tidak valid / magic bytes tidak cocok"}}`
- `413 Payload Too Large`: `{"error": {"code": 413, "message": "Ukuran berkas melebihi batas 25MB"}}`
- `429 Too Many Requests`: `{"error": {"code": 429, "message": "Anda masih memiliki proses analisis yang berjalan"}}`

---

### `GET /api/jobs/{jobId}`
Memeriksa status kemajuan analisis audio secara berkala (*polling*).

**Headers:**
```
Authorization: Bearer <token>
```

**Respons (200 OK - Sedang Berjalan):**
```json
{
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "transcribing",
  "progress": 45,
  "errorMessage": null
}
```

**Respons (200 OK - Selesai):**
```json
{
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "status": "done",
  "progress": 100,
  "errorMessage": null
}
```

---

### `GET /api/results/{jobId}`
Mengambil laporan hasil analisis lengkap ketika status job telah mencapai `"done"`.

**Headers:**
```
Authorization: Bearer <token>
```

**Respons Sukses (200 OK):**
```json
{
  "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "label": "SCAM",
  "scamCategory": "BANK_IMPERSONATION",
  "riskScore": 94,
  "riskLevel": "Critical",
  "explanation": "Panggilan ini teridentifikasi sebagai upaya penipuan mengatasnamakan Bank Mandiri. Pelaku meminta kode OTP SMS rahasia dengan ancaman rekening akan diblokir dalam 15 menit.",
  "indicators": [
    {
      "code": "IND_OTP",
      "name": "Permintaan Kode OTP",
      "weight": 30,
      "quote": "mohon sebutkan kode otp **** yang baru saja masuk ke sms anda sekarang"
    },
    {
      "code": "IND_CLAIM_BANK",
      "name": "Klaim dari Lembaga Keuangan",
      "weight": 15,
      "quote": "halo selamat siang kami dari customer service bank mandiri pusat"
    },
    {
      "code": "IND_BLOCKING",
      "name": "Ancaman Pemblokiran Rekening",
      "weight": 15,
      "quote": "apabila tidak diverifikasi maka rekening anda akan diblokir otomatis"
    }
  ],
  "transcript": [
    {
      "start": 0.0,
      "end": 3.8,
      "text": "Halo selamat siang kami dari customer service Bank Mandiri pusat",
      "flagged": true
    },
    {
      "start": 3.8,
      "end": 8.5,
      "text": "Mohon sebutkan kode OTP **** yang baru saja masuk ke SMS anda sekarang",
      "flagged": true
    },
    {
      "start": 8.5,
      "end": 12.0,
      "text": "Apabila tidak diverifikasi maka rekening anda akan diblokir otomatis",
      "flagged": true
    }
  ],
  "overrideApplied": false
}
```

---

## 4. Riwayat Analisis (Opt-in)

### `GET /api/history`
Mengambil daftar riwayat hasil analisis milik pengguna dengan paginasi (hanya jika pengguna mengaktifkan `saveHistory: true`).

**Query Parameters:**
- `page`: Nomor halaman (integer, default `1`).
- `limit`: Jumlah data per halaman (integer, default `10`, maks `50`).

**Respons Sukses (200 OK):**
```json
{
  "total": 1,
  "page": 1,
  "limit": 10,
  "items": [
    {
      "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "jobId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "label": "SCAM",
      "scamCategory": "BANK_IMPERSONATION",
      "riskScore": 94,
      "riskLevel": "Critical",
      "explanation": "Panggilan terindikasi penipuan perbankan meminta OTP.",
      "createdAt": "2026-11-14T10:30:00Z",
      "expiresAt": "2026-12-14T10:30:00Z"
    }
  ]
}
```

---

### `DELETE /api/results/{id}`
Menghapus riwayat analisis tertentu dari database (*Right to be Forgotten*).

**Headers:**
```
Authorization: Bearer <token>
```

**Respons Sukses (200 OK):**
```json
{
  "message": "Riwayat analisis berhasil dihapus",
  "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```
