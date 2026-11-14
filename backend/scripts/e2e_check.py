import os
import sys
import time
import io
import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def generate_dummy_wav() -> bytes:
    sample_rate = 16000
    duration_sec = 4
    num_channels = 1
    bits = 16
    data_size = duration_sec * sample_rate * num_channels * (bits // 8)
    file_size = 36 + data_size

    header = bytearray()
    header.extend(b"RIFF")
    header.extend(file_size.to_bytes(4, "little"))
    header.extend(b"WAVEfmt ")
    header.extend((16).to_bytes(4, "little"))
    header.extend((1).to_bytes(2, "little"))
    header.extend(num_channels.to_bytes(2, "little"))
    header.extend(sample_rate.to_bytes(4, "little"))
    header.extend((sample_rate * num_channels * (bits // 8)).to_bytes(4, "little"))
    header.extend((num_channels * (bits // 8)).to_bytes(2, "little"))
    header.extend(bits.to_bytes(2, "little"))
    header.extend(b"data")
    header.extend(data_size.to_bytes(4, "little"))
    header.extend(b"\x00" * data_size)
    return bytes(header)


def run_e2e():
    print(f"[E2E] Menghubungkan ke API di {BASE_URL}...")

    # 1. Cek Health
    try:
        h = requests.get(f"{BASE_URL}/api/health", timeout=5).json()
        print(f"[OK] Health Status: {h.get('status')} | Version: {h.get('version')}")
    except Exception as e:
        print(f"[ERROR] Backend tidak dapat dihubungi di {BASE_URL}: {e}")
        sys.exit(1)

    # 2. Login / Register
    email = f"e2e_test_{int(time.time())}@example.com"
    pw = "Password123"
    print(f"[E2E] Mendaftarkan user uji: {email}...")

    reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
        "nama": "E2E Tester",
        "email": email,
        "password": pw
    })
    if reg_res.status_code == 201:
        token = reg_res.json()["token"]
    else:
        # Fallback login
        login_res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
        token = login_res.json()["token"]

    headers = {"Authorization": f"Bearer {token}"}
    print("[OK] Autentikasi berhasil!")

    # 3. Upload Audio
    print("[E2E] Mengunggah file audio uji...")
    audio_data = generate_dummy_wav()
    files = {"file": ("test_e2e.wav", io.BytesIO(audio_data), "audio/wav")}
    upload_res = requests.post(
        f"{BASE_URL}/api/analyze",
        headers=headers,
        files=files,
        data={"saveHistory": "true"}
    )
    if upload_res.status_code != 202:
        print(f"[FAIL] Upload gagal: {upload_res.status_code} - {upload_res.text}")
        sys.exit(1)

    job_id = upload_res.json()["jobId"]
    print(f"[OK] Analisis dijadwalkan dengan Job ID: {job_id}")

    # 4. Polling Status Job
    print("[E2E] Memulai polling status job...")
    for _ in range(30):
        time.sleep(1)
        job_res = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=headers).json()
        status_name = job_res.get("status")
        progress = job_res.get("progress", 0)
        print(f"Status: {status_name} | Progres: {progress}%")

        if status_name == "done":
            break
        elif status_name == "failed":
            print(f"[FAIL] Analisis gagal: {job_res.get('errorMessage')}")
            sys.exit(1)

    # 5. Ambil Hasil Lengkap
    print("\n[E2E] Mengambil hasil analisis...")
    res = requests.get(f"{BASE_URL}/api/results/{job_id}", headers=headers).json()
    print("=" * 60)
    print(f"Label Risiko    : {res.get('label')}")
    print(f"Tingkat Risiko  : {res.get('riskLevel')} (Skor: {res.get('riskScore')})")
    print(f"Kategori Scam   : {res.get('scamCategory')}")
    print(f"Override Aktif  : {res.get('overrideApplied')}")
    print(f"Penjelasan      : {res.get('explanation')}")
    print(f"Indikator ({len(res.get('indicators', []))}):")
    for ind in res.get("indicators", []):
        print(f"  - [{ind['code']}] {ind['label']} (Bobot: {ind['weight']}) -> '{ind['quote']}'")
    print("=" * 60)
    print("[SUCCESS] Pengujian End-to-End SAVESPEECH selesai dengan sukses!")


if __name__ == "__main__":
    run_e2e()
