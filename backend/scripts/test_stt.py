import sys
import os
import asyncio
from pathlib import Path

# Tambahkan path backend ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.stt import transcribe, STTException


async def run_stt_cli(file_path_str: str):
    path = Path(file_path_str)
    if not path.exists():
        print(f"[ERROR] File audio tidak ditemukan: {path}")
        sys.exit(1)

    print(f"[INFO] Memulai transkripsi untuk: {path.name}...")

    def on_progress(pct: int):
        print(f"Progres transkripsi: {pct}%", end="\r")

    try:
        segments = await transcribe(path, on_progress=on_progress)
        print("\n--- HASIL TRANSKRIPSI BERSTEMPEL WAKTU ---")
        for seg in segments:
            start_fmt = f"{int(seg['start'] // 60):02d}:{int(seg['start'] % 60):02d}"
            end_fmt = f"{int(seg['end'] // 60):02d}:{int(seg['end'] % 60):02d}"
            print(f"[{start_fmt} - {end_fmt}] {seg['text']}")
        print("------------------------------------------")
    except STTException as e:
        print(f"\n[ERROR] STT gagal dengan kode [{e.code}]: {e.message}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Kesalahan tak terduga: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python scripts/test_stt.py <path_to_audio_file>")
        sys.exit(1)

    asyncio.run(run_stt_cli(sys.argv[1]))


if __name__ == "__main__":
    main()
