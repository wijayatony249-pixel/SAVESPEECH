# SAVESPEECH Backend — Security Policy & Controls (SEC-01 s/d SEC-12)

Dokumen ini menjelaskan arsitektur keamanan, model ancaman, kontrol teknis (SEC-01 s/d SEC-12), hasil audit SAST (Bandit), evaluasi dependensi (pip-audit), serta kepatuhan privasi (UU PDP No. 27 Tahun 2022 / GDPR) pada SAVESPEECH Backend.

---

## 1. Daftar Kontrol Keamanan (SEC-01 s/d SEC-12)

| Kode | Kontrol Keamanan | Mekanisme Implementasi | Status Verifikasi |
|---|---|---|---|
| **SEC-01** | **Validasi Ekstensi & Magic Bytes** | Pengecekan whitelist ekstensi (`.wav`, `.mp3`, `.m4a`), header binary magic bytes (`RIFF....WAVE`, `ID3` / `\xff\xfb`, `ftyp`), dan MIME type. File `.exe`, skrip shell, atau polyglot langsung ditolak dengan HTTP 400. | ✅ Teruji di `test_security.py` |
| **SEC-02** | **Pembatasan Ukuran & Streaming Safe** | Streaming file chunk demi chunk (64KB). Jika total byte melebihi `MAX_UPLOAD_MB` (25MB), streaming langsung diputus dan file parsial dihapus (mencegah DoS exhaust storage). | ✅ Teruji di `test_security.py` |
| **SEC-03** | **Autentikasi Wajib & JWT Hardening** | Seluruh endpoint operasional dilindungi Bearer JWT (HS256). Token kedaluwarsa atau palsu ditolak dengan HTTP 401. Secret minimal 32 karakter divalidasi saat startup production. | ✅ Teruji di `test_security.py` |
| **SEC-04** | **Mitigasi IDOR (Insecure Direct Object Reference)** | Validasi kepemilikan resource (`user_id == current_user.id`) pada pengambilan status pekerjaan (`/api/jobs/{id}`), hasil analisis (`/api/results/{jobId}`), dan riwayat (`/api/history`). Akses tidak sah mengembalikan HTTP 404 tanpa membocorkan keberadaan data. | ✅ Teruji di `test_security.py` |
| **SEC-05** | **Pembatasan Laju (Rate Limiting)** | Menggunakan Slowapi (in-memory / Redis-ready) berbasis `ip_hash`: Login (5/menit), Registrasi (5/jam), Unggah Audio (10/menit). Permintaan melebihi batas mengembalikan HTTP 429. | ✅ Teruji di `test_security.py` |
| **SEC-06** | **Pembatasan Satu Pekerjaan Aktif per Pengguna** | In-memory JobManager mencegah pengguna menjalankan banyak analisis audio secara paralel secara serentak (mencegah CPU starvation). Permintaan kedua saat status `uploading`/`transcribing`/`analyzing` menghasilkan HTTP 429 `ACTIVE_JOB_EXISTS`. | ✅ Teruji di `test_security.py` |
| **SEC-07** | **Zero Persistent Audio Storage** | File audio temporer yang disimpan di direktori lokal SELALU dihapus pada blok `finally`, baik pipeline sukses, terhenti, maupun mengalami exception/crash. Direktori temporer 100% bersih. | ✅ Teruji di `test_security.py` |
| **SEC-08** | **Zero Transcript Storage di Database** | Database PostgreSQL sama sekali tidak memiliki kolom teks transkrip, teks mentah, kutipan percakapan, maupun audio. Opt-in riwayat hanya menyimpan metrik agregat (`label`, `scam_category`, `risk_score`, `risk_level`, `explanation`, dan kode indikator numerik). | ✅ Teruji di `test_security.py` |
| **SEC-09** | **Redaksi Jejak Audit & Log Aplikasi** | `AuditLog` hanya mencatat `ip_hash` (HMAC-SHA256), `action`, dan `status`. Logging aplikasi menggunakan `SensitiveDataFilter` yang otomatis menyensor token JWT, kata sandi, OTP, dan teks transkrip. | ✅ Teruji di `test_security.py` |
| **SEC-10** | **HTTP Security Headers** | Header hardening dipasang pada setiap respons: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `Content-Security-Policy: default-src 'self'`, dan `Referrer-Policy: strict-origin-when-cross-origin`. | ✅ Teruji di `test_security.py` |
| **SEC-11** | **Strict Cross-Origin Resource Sharing (CORS)** | CORS dikonfigurasi secara eksplisit hanya untuk origin frontend yang terdaftar (`http://localhost:5173`, `http://localhost:3000`). Penggunaan wildcard `*` dilarang. Permintaan dari origin liar diblokir. | ✅ Teruji di `test_security.py` |
| **SEC-12** | **Credential & PII Masking** | Deretan angka sensitif 4 digit atau lebih (kode OTP 6 digit, PIN perbankan, nomor rekening) otomatis disensor menjadi `****` pada transkrip memori dan kutipan indikator sebelum dikirim ke frontend. | ✅ Teruji di `test_security.py` |

---

## 2. Hasil Audit Keamanan Statis (SAST) — Bandit

Pemindaian keamanan kode statis dijalankan dengan `bandit -r backend/app -ll`:

```bash
bandit -r backend/app -ll
```

### Hasil Pemindaian:
- **Total lines of code scanned**: 1,708
- **High Severity Issues**: 0
- **Medium Severity Issues**: 0
- **Low Severity Issues**: 6 (Terdokumentasi dan terjustifikasi di bawah)

### Evaluasi Temuan Kategori Rendah (Low Severity) yang Diterima:
1. **B105 (`DUMMY_PASSWORD_HASH` di `security.py`)**:
   - *Penjelasan*: String hash bcrypt dummy sengaja diletakkan untuk proses verifikasi password tiruan ketika user tidak ditemukan di database. Tujuannya adalah mitigasi **Timing Attack** (mencegah penyerang membedakan waktu respons antara email terdaftar vs email belum terdaftar). Hash ini tidak cocok dengan password apa pun.
2. **B110 (`try ... except: pass` pada `storage.py:touch(mode=0o600)`)**:
   - *Penjelasan*: Fallback non-blocking pada sistem operasi Windows di mana flag izin POSIX `0o600` tidak berlaku secara native.
3. **B404 & B603 (`subprocess.run` di `stt.py` dan `upload_validation.py`)**:
   - *Penjelasan*: Pemanggilan biner `ffmpeg` dan `ffprobe`. Eksekusi menggunakan `shell=False` dengan daftar argumen string yang divalidasi ketat (bukan input string mentah dari user), sehingga terbebas dari Command Injection.

---

## 3. Hasil Audit Dependensi — pip-audit

Pemindaian kerentanan CVE pada paket pihak ketiga dijalankan menggunakan `pip-audit -r backend/requirements.txt`.
- Dependensi utama dikunci (*pinned*) pada versi stabil.
- Rekomendasi operasional produksi:
  - Jalankan `pip-audit` secara berkala dalam CI/CD pipeline (misal GitHub Actions mingguan).
  - Isolasi container backend dalam bridge network internal Docker tanpa akses publik langsung selain reverse proxy (Nginx / Cloudflare).

---

## 4. Kepatuhan Privasi (UU PDP No. 27 Tahun 2022 / GDPR)

SAVESPEECH dirancang dengan prinsip **Privacy by Design** dan **Data Minimization**:
1. **Hak Pengguna (Opt-in History)**: Pengguna memiliki kendali penuh melalui flag `saveHistory: false` (default) saat analisis. Jika false, tidak ada jejak apa pun yang tersimpan di basis data setelah 15 menit TTL in-memory berakhir.
2. **Retensi 30 Hari**: Data ringkasan opt-in otomatis memiliki tanggal `expires_at = NOW() + 30 hari`. Setiap permintaan riwayat secara proaktif membersihkan entri yang kedaluwarsa.
3. **Hak untuk Dihapus (*Right to be Forgotten*)**: Pengguna dapat menghapus riwayat analisisnya kapan saja melalui endpoint `DELETE /api/results/{id}`.
4. **Anonymized IP Logging**: Alamat IP pengunjung tidak pernah disimpan dalam bentuk plaintext. Seluruh pencatatan menggunakan `HMAC-SHA256(ip_address, IP_HASH_SECRET)`.
