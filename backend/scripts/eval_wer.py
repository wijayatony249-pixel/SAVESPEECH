import sys
import os
import asyncio
from pathlib import Path
import jiwer

# Tambahkan path backend ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.stt import transcribe, STTException


async def evaluate_wer_folder(folder_path_str: str):
    folder = Path(folder_path_str)
    if not folder.exists() or not folder.is_dir():
        print(f"[ERROR] Direktori tidak ditemukan: {folder}")
        sys.exit(1)

    audio_extensions = {".wav", ".mp3", ".m4a"}
    audio_files = [f for f in folder.iterdir() if f.suffix.lower() in audio_extensions]

    if not audio_files:
        print(f"[WARN] Tidak ditemukan file audio di {folder}")
        return

    wer_results = []
    print(f"[INFO] Mengevaluasi {len(audio_files)} berkas audio terhadap referensi .txt...")
    print("-" * 65)
    print(f"{'Nama File':<30} | {'Status':<10} | {'WER':<10}")
    print("-" * 65)

    for audio_file in audio_files:
        ref_file = audio_file.with_suffix(".txt")
        if not ref_file.exists():
            print(f"{audio_file.name:<30} | {'NO_REF':<10} | {'-':<10}")
            continue

        reference_text = ref_file.read_text(encoding="utf-8").strip()

        try:
            segments = await transcribe(audio_file)
            hypothesis_text = " ".join(seg["text"] for seg in segments).strip()

            error_rate = jiwer.wer(reference_text, hypothesis_text)
            wer_results.append((audio_file.name, error_rate))
            print(f"{audio_file.name:<30} | {'OK':<10} | {error_rate * 100:.2f}%")
        except STTException as e:
            print(f"{audio_file.name:<30} | {e.code:<10} | {'-':<10}")
        except Exception as e:
            print(f"{audio_file.name:<30} | {'ERROR':<10} | {str(e)[:15]}")

    print("-" * 65)
    if wer_results:
        avg_wer = sum(r[1] for r in wer_results) / len(wer_results)
        print(f"RATA-RATA WER: {avg_wer * 100:.2f}% (Target PRD: <= 25.00%)")
        if avg_wer <= 0.25:
            print("[STATUS] MEMENUHI SYARAT PRD (BE-NFR-02)")
        else:
            print("[WARN] Melebihi ambang batas WER target PRD")
    else:
        print("[INFO] Tidak ada data pengujian yang berhasil dievaluasi.")


def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python scripts/eval_wer.py <folder_berisi_audio_dan_referensi_txt>")
        sys.exit(1)

    asyncio.run(evaluate_wer_folder(sys.argv[1]))


if __name__ == "__main__":
    main()
