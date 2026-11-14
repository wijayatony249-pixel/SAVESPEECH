import os
import random
import pandas as pd
from pathlib import Path

RANDOM_SEED = 42

DATASET_DIR = Path(__file__).resolve().parent
RAW_CSV = DATASET_DIR / "dataset_raw.csv"


def split_dataset():
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"File raw dataset tidak ditemukan di: {RAW_CSV}")

    df = pd.read_csv(RAW_CSV)
    print(f"[INFO] Memuat {len(df)} data dari {RAW_CSV.name}...")

    train_rows = []
    val_rows = []
    test_rows = []

    # Pisahkan template per kelas label
    for label in ["NORMAL", "SUSPICIOUS", "SCAM"]:
        sub_df = df[df["label"] == label].copy()
        unique_templates = sorted(sub_df["template_id"].unique())
        
        # Acak urutan template secara deterministik
        rng = random.Random(RANDOM_SEED + hash(label))
        rng.shuffle(unique_templates)

        n_t = len(unique_templates)
        # Tentukan pembagian template: ~70% train, ~15% val, ~15% test
        n_val = max(1, round(n_t * 0.15))
        n_test = max(1, round(n_t * 0.15))
        n_train = n_t - n_val - n_test

        train_tmpl = set(unique_templates[:n_train])
        val_tmpl = set(unique_templates[n_train:n_train + n_val])
        test_tmpl = set(unique_templates[n_train + n_val:])

        train_rows.append(sub_df[sub_df["template_id"].isin(train_tmpl)])
        val_rows.append(sub_df[sub_df["template_id"].isin(val_tmpl)])
        test_rows.append(sub_df[sub_df["template_id"].isin(test_tmpl)])

    train_df = pd.concat(train_rows, ignore_index=True)
    val_df = pd.concat(val_rows, ignore_index=True)
    test_df = pd.concat(test_rows, ignore_index=True)

    # 1. ASSERT ANTI-LEAKAGE: Pastikan tidak ada template_id yang bocor antar split
    train_templates = set(train_df["template_id"].unique())
    val_templates = set(val_df["template_id"].unique())
    test_templates = set(test_df["template_id"].unique())

    overlap_train_val = train_templates.intersection(val_templates)
    overlap_train_test = train_templates.intersection(test_templates)
    overlap_val_test = val_templates.intersection(test_templates)

    assert len(overlap_train_val) == 0, f"LEAKAGE: Template tumpang tindih antara Train & Val: {overlap_train_val}"
    assert len(overlap_train_test) == 0, f"LEAKAGE: Template tumpang tindih antara Train & Test: {overlap_train_test}"
    assert len(overlap_val_test) == 0, f"LEAKAGE: Template tumpang tindih antara Val & Test: {overlap_val_test}"

    # 2. Pastikan setiap split memiliki kelas SCAM, NORMAL, dan SUSPICIOUS
    for split_name, s_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        classes = set(s_df["label"].unique())
        assert len(classes) == 3, f"Split {split_name} kekurangan kelas: {classes}"

    # Simpan ke CSV
    train_path = DATASET_DIR / "train.csv"
    val_path = DATASET_DIR / "val.csv"
    test_path = DATASET_DIR / "test.csv"

    train_df.to_csv(train_path, index=False, encoding="utf-8")
    val_df.to_csv(val_path, index=False, encoding="utf-8")
    test_df.to_csv(test_path, index=False, encoding="utf-8")

    print(f"\n[SUCCESS] Split dataset 70/15/15 selesai tanpa kebocoran template!")
    print(f"- Train : {len(train_df)} baris ({len(train_templates)} templates) -> {train_path.name}")
    print(f"- Val   : {len(val_df)} baris ({len(val_templates)} templates) -> {val_path.name}")
    print(f"- Test  : {len(test_df)} baris ({len(test_templates)} templates) -> {test_path.name}")

    print("\n--- DISTRIBUSI KELAS PER SPLIT ---")
    for name, split_df in [("Train", train_df), ("Val", val_df), ("Test", test_df)]:
        print(f"\n[{name} Set - Total: {len(split_df)}]:")
        print(split_df["label"].value_counts().to_string())


if __name__ == "__main__":
    split_dataset()
