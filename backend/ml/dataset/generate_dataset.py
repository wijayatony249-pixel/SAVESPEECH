import os
import random
import uuid
import pandas as pd
from pathlib import Path

# Seed tetap untuk reprodusibilitas
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

DATASET_DIR = Path(__file__).resolve().parent

INSTITUTIONS = [
    "Bank Nusantara", "Bank Artha Makmur", "Bank Dana Sejahtera",
    "Bank Amanah Indonesia", "Bank Central Sejahtera",
]

E_WALLETS = [
    "DompetKilat", "PayNusantara", "KantongPay", "KasDigital", "DanaCepat"
]

TITLES = ["Bapak", "Ibu", "Kakak", "Saudara"]
NAMES = ["Budi", "Siti", "Hendra", "Dewi", "Rian", "Maya", "Agus", "Lestari", "Doni", "Putri", "Eko", "Ani"]

AMOUNTS = [
    "2.500.000 rupiah", "5.000.000 rupiah", "7.800.000 rupiah",
    "12.000.000 rupiah", "15.500.000 rupiah", "850.000 rupiah"
]

TIME_LIMITS = [
    "dalam 5 menit ke depan", "segera dalam 10 menit", "sekarang juga",
    "sebelum sistem menutup otomatis", "sebelum pukul 12 siang ini"
]

FILLERS = [
    "ehm", "eeh", "baik", "mohon perhatiannya", "mohon disimak", "harap tenang", ""
]

# 1. TEMPLATES NORMAL (10 Template ID unik -> 200 data)
NORMAL_TEMPLATES = [
    {"id": "NORM_KURIR_1", "category": None, "indicators": [], "t": "Halo selamat siang {title} {name}, ini dari kurir ekspedisi. Paket bapak sudah sampai di pos satpam. Mohon diambil ya."},
    {"id": "NORM_KURIR_2", "category": None, "indicators": [], "t": "Siang {title}, saya kurir mengantar pesanan online bapak. Pintu gerbang terkunci, apa paketnya boleh saya titipkan ke tetangga sebelah?"},
    {"id": "NORM_KELUARGA_1", "category": None, "indicators": [], "t": "Halo {name}, nanti sore jadi mampir ke rumah kan? Ibu lagi masak rawon kesukaan kamu nih. Jangan telat ya."},
    {"id": "NORM_KELUARGA_2", "category": None, "indicators": [], "t": "Hai bro {name}, besok kuliah jam berapa? Jangan lupa bawa buku catatan yang kemarin kamu pinjam ya."},
    {"id": "NORM_TELE_1", "category": None, "indicators": [], "t": "Selamat pagi {title} {name}, kami dari {institution} ingin menawarkan program tabungan berjangka bunga promo. Jika tertarik bapak bisa ke kantor cabang."},
    {"id": "NORM_TELE_2", "category": None, "indicators": [], "t": "Halo selamat siang {title}, perkenalkan saya dari asuransi kesehatan mitra {institution}. Kami memiliki promo perlindungan keluarga tanpa biaya tambahan."},
    {"id": "NORM_HARDNEG_1", "category": None, "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO"], "t": "Pemberitahuan resmi dari {institution}. Terdeteksi upaya login m-banking bapak dari HP baru. Jika bukan bapak, ganti password di aplikasi. Pihak bank tidak pernah meminta kode OTP atau PIN Anda."},
    {"id": "NORM_HARDNEG_2", "category": None, "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO"], "t": "Halo {title} {name}, kami dari tim keamanan {institution}. Sistem mendeteksi transaksi luar kota. Mohon jangan pernah berikan kode verifikasi OTP atau kata sandi kepada siapa pun termasuk staf bank."},
    {"id": "NORM_CS_1", "category": None, "indicators": [], "t": "Selamat pagi {title} {name}, kami menindaklanjuti tiket pengaduan internet Anda kemarin. Apakah koneksi di rumah saat ini sudah kembali lancar?"},
    {"id": "NORM_CS_2", "category": None, "indicators": [], "t": "Siang {title} {name}, reservasi meja Anda di restoran kami untuk malam minggu besok pukul 7 malam sudah kami catat ya."},
]

# 2. TEMPLATES SUSPICIOUS (8 Template ID unik -> 150 data)
SUSPICIOUS_TEMPLATES = [
    {"id": "SUSP_TX_1", "category": None, "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO"], "t": "Selamat siang {title} {name}, kami dari pemantau transaksi {institution}. Terdeteksi ada penarikan {nominal} di ATM luar daerah. Apakah benar ini aktivitas bapak sendiri?"},
    {"id": "SUSP_TX_2", "category": None, "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO", "URGENCY"], "t": "Halo {title}, saya menghubungi dari tim fraud {institution}. Rekening bapak tercatat melakukan gesek tunai {nominal}. Mohon konfirmasi apakah bapak sedang di toko tersebut?"},
    {"id": "SUSP_DATA_1", "category": None, "indicators": ["CLAIM_INSTITUTION", "URGENCY"], "t": "Selamat sore {title} {name}, akun {institution} bapak belum diperbarui sesuai regulasi terbaru. Jika minggu ini tidak ke cabang, beberapa fitur transaksi akan dibatasi."},
    {"id": "SUSP_DATA_2", "category": None, "indicators": ["CLAIM_INSTITUTION"], "t": "Halo {title}, kami dari bagian kepatuhan data nasabah {institution}. Ada perbedaan data alamat pada akun bapak. Segera hubungi kantor cabang terdekat bapak."},
    {"id": "SUSP_REWARD_1", "category": None, "indicators": ["CLAIM_INSTITUTION"], "t": "Selamat siang {title} {name}, nomor bapak terpilih mendapatkan reward cashback {nominal} dari {ewallet}. Silakan buka aplikasi Anda untuk melihat apakah voucher sudah aktif."},
    {"id": "SUSP_REWARD_2", "category": None, "indicators": ["CLAIM_INSTITUTION"], "t": "Halo bapak, selamat nomor rekening bapak di {institution} memenangkan undian poin nasabah setia. Hadiah bisa diklaim di kantor cabang terdekat bapak."},
    {"id": "SUSP_PINJOL_1", "category": None, "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO"], "t": "Panggilan dari verifikator {institution}. Ada permohonan pinjaman online senilai {nominal} menggunakan KTP atas nama {title} {name}. Benarkah bapak yang mengajukannya?"},
    {"id": "SUSP_SKIM_1", "category": None, "indicators": ["CLAIM_INSTITUTION", "URGENCY"], "t": "Halo {title}, kami menerima laporan bahwa kartu ATM Anda terindikasi skimming di mesin SPBU. Kami himbau segera cek saldo mutasi bapak."},
]

# 3. TEMPLATES SCAM (15 Template ID unik, 3 per kategori -> 250 data)
SCAM_TEMPLATES = [
    # BANK_IMPERSONATION (3 templates)
    {"id": "SCAM_BANK_1", "category": "BANK_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "SUSPICIOUS_TX_INFO", "REQ_OTP", "URGENCY"], "t": "Halo selamat siang {title} {name}, saya dari petugas keamanan sentral {institution}. Terjadi penarikan ilegal {nominal} di kartu bapak. Untuk membatalkan transaksi sekarang {time_limit}, segera sebutkan 6 digit kode OTP SMS bapak!"},
    {"id": "SCAM_BANK_2", "category": "BANK_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "REQ_CREDENTIAL", "REQ_OTP", "URGENCY"], "t": "Selamat pagi {title}, ini CS pusat {institution}. Kartu debit bapak sedang dibobol di luar negeri sebesar {nominal}. Agar saldo aman, segera beritahukan kode PIN dan kode OTP SMS sekarang kepada saya!"},
    {"id": "SCAM_BANK_3", "category": "BANK_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "REQ_CREDENTIAL", "URGENCY"], "t": "Halo dengan {title} {name}? Saya kepala audit {institution}. Ada gesekan mencurigakan {nominal}. Berikan nomor kartu dan 3 angka CVV di belakang kartu Anda untuk kami batalkan tagihannya!"},

    # E_WALLET_IMPERSONATION (3 templates)
    {"id": "SCAM_EWAL_1", "category": "E_WALLET_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "REQ_OTP", "URGENCY"], "t": "Halo kak {name}, kami dari pihak resmi {ewallet}. Akun dompet digital kakak sedang dicoba login dari perangkat lain. Kami akan bantu amankan, tolong sebutkan kode OTP SMS yang baru masuk ke handphone sekarang!"},
    {"id": "SCAM_EWAL_2", "category": "E_WALLET_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "REQ_OTP", "URGENCY"], "t": "Selamat siang {title}, akun {ewallet} Anda terpilih mendapatkan bonus saldo {nominal}. Untuk pencairan dana ke rekening Anda {time_limit}, mohon kirimkan kode verifikasi OTP yang kami kirimkan ke nomor HP Anda!"},
    {"id": "SCAM_EWAL_3", "category": "E_WALLET_IMPERSONATION", "indicators": ["CLAIM_INSTITUTION", "REQ_CREDENTIAL", "REQ_OTP", "BLOCK_THREAT"], "t": "Halo bapak dari customer care {ewallet}. Akun Anda melanggar kebijakan. Segera bacakan kode OTP dan PIN akun Anda agar akun tidak diblokir permanen oleh sistem pusat kami!"},

    # OTP_SCAM (3 templates)
    {"id": "SCAM_OTP_1", "category": "OTP_SCAM", "indicators": ["REQ_OTP", "URGENCY"], "t": "Halo selamat siang bapak, saya tidak sengaja salah memasukkan nomor HP saat mau beli voucher, dan kodenya terkirim ke SMS bapak. Tolong bacakan 6 digit angka kode OTP yang barusan masuk ke SMS bapak ya!"},
    {"id": "SCAM_OTP_2", "category": "OTP_SCAM", "indicators": ["REQ_OTP", "URGENCY", "PSYCHOLOGICAL_MANIP"], "t": "Permisi {title} {name}, kasir minimarket salah input nomor kupon undian dan masuk ke handphone Anda. Mohon bantuannya sebutkan kode angka SMS yang barusan masuk, sangat mendesak {time_limit}!"},
    {"id": "SCAM_OTP_3", "category": "OTP_SCAM", "indicators": ["REQ_OTP", "URGENCY"], "t": "Selamat siang kak, saya rekan kerja kantor bapak. Server kantor mengirim kode sandi OTP ke HP bapak. Tolong segera bacakan kodenya sekarang saya butuh cepat {time_limit}!"},

    # TRANSFER_SCAM (3 templates)
    {"id": "SCAM_TRF_1", "category": "TRANSFER_SCAM", "indicators": ["CLAIM_INSTITUTION", "TRANSFER_INSTRUCTION", "URGENCY", "PSYCHOLOGICAL_MANIP"], "t": "Halo {title} {name}, dari kepolisian cyber crime bekerjasama dengan {institution}. Rekening bapak terindikasi pencucian uang. Untuk menyelamatkan saldo {nominal}, segera pindahkan dana ke rekening penampungan aman khusus kepolisian {time_limit}!"},
    {"id": "SCAM_TRF_2", "category": "TRANSFER_SCAM", "indicators": ["CLAIM_INSTITUTION", "TRANSFER_INSTRUCTION", "URGENCY"], "t": "Peringatan investigasi keuangan {institution}! Rekening Anda diretas. Demi mengamankan dana bapak, ikuti instruksi saya ke mesin ATM terdekat sekarang juga dan transfer saldo ke rekening aman sementara milik bank kami!"},
    {"id": "SCAM_TRF_3", "category": "TRANSFER_SCAM", "indicators": ["CLAIM_INSTITUTION", "TRANSFER_INSTRUCTION", "URGENCY"], "t": "Halo selamat sore {title}, ada kesalahan sistem auto-debet {nominal} pada tabungan Anda. Segera lakukan transfer pengembalian dana ke rekening virtual account aman yang kami sediakan sebelum sistem terkunci!"},

    # ACCOUNT_BLOCKING_SCAM (3 templates)
    {"id": "SCAM_BLK_1", "category": "ACCOUNT_BLOCKING_SCAM", "indicators": ["CLAIM_INSTITUTION", "BLOCK_THREAT", "APP_LINK_INSTRUCTION", "REQ_CREDENTIAL"], "t": "Pemberitahuan darurat {institution}! Rekening dan kartu ATM bapak {name} akan DIBLOKIR TOTAL dalam waktu 15 menit. Klik tautan pemulihan yang kami kirim di SMS dan masukkan PIN serta password m-banking Anda sekarang!"},
    {"id": "SCAM_BLK_2", "category": "ACCOUNT_BLOCKING_SCAM", "indicators": ["CLAIM_INSTITUTION", "BLOCK_THREAT", "APP_LINK_INSTRUCTION", "REQ_OTP"], "t": "Halo {title}, akun perbankan bapak terkena pemblokiran sistem. Jangan biarkan kartu Anda disita ATM. Cepat unduh aplikasi link APK pemulihan yang kami kirimkan ke WhatsApp dan masukkan kode OTP agar blokir terbuka!"},
    {"id": "SCAM_BLK_3", "category": "ACCOUNT_BLOCKING_SCAM", "indicators": ["CLAIM_INSTITUTION", "BLOCK_THREAT", "REQ_CREDENTIAL", "REQ_OTP", "URGENCY"], "t": "Panggilan resmi penutupan rekening {institution}! Jika bapak tidak segera konfirmasi identitas dengan menyebutkan PIN ATM dan OTP dalam 5 menit ini, semua saldo bapak akan hangus dan dibekukan permanen!"},
]


def fill_slots(template_str: str) -> str:
    institution = random.choice(INSTITUTIONS)
    ewallet = random.choice(E_WALLETS)
    title = random.choice(TITLES)
    name = random.choice(NAMES)
    nominal = random.choice(AMOUNTS)
    time_limit = random.choice(TIME_LIMITS)
    filler = random.choice(FILLERS)

    text = template_str.format(
        institution=institution,
        ewallet=ewallet,
        title=title,
        name=name,
        nominal=nominal,
        time_limit=time_limit,
    )
    if filler:
        text = f"{filler}, {text}"
    return text.strip()


def build_synthetic_dataset() -> pd.DataFrame:
    rows = []

    # 1. NORMAL: 200 data dibagi ke 10 template (20 per template)
    for grp in NORMAL_TEMPLATES:
        for _ in range(20):
            rows.append({
                "id": str(uuid.uuid4()),
                "transcript": fill_slots(grp["t"]),
                "label": "NORMAL",
                "scam_category": grp["category"],
                "indicators": ";".join(grp["indicators"]),
                "template_id": grp["id"],
            })

    # 2. SUSPICIOUS: 150 data dibagi ke 8 template (~19 per template)
    susp_counts = [19] * 8
    susp_counts[0] += 1  # 150 total
    susp_counts[1] += 1
    for i, grp in enumerate(SUSPICIOUS_TEMPLATES):
        for _ in range(susp_counts[i]):
            rows.append({
                "id": str(uuid.uuid4()),
                "transcript": fill_slots(grp["t"]),
                "label": "SUSPICIOUS",
                "scam_category": grp["category"],
                "indicators": ";".join(grp["indicators"]),
                "template_id": grp["id"],
            })

    # 3. SCAM: 250 data dibagi ke 15 template (3 per kategori, 50 per kategori)
    # Tiap kategori: 17 + 17 + 16 = 50 data
    scam_cats = ["BANK_IMPERSONATION", "E_WALLET_IMPERSONATION", "OTP_SCAM", "TRANSFER_SCAM", "ACCOUNT_BLOCKING_SCAM"]
    for cat in scam_cats:
        cat_templates = [t for t in SCAM_TEMPLATES if t["category"] == cat]
        counts = [17, 17, 16]
        for idx, grp in enumerate(cat_templates):
            for _ in range(counts[idx]):
                rows.append({
                    "id": str(uuid.uuid4()),
                    "transcript": fill_slots(grp["t"]),
                    "label": "SCAM",
                    "scam_category": grp["category"],
                    "indicators": ";".join(grp["indicators"]),
                    "template_id": grp["id"],
                })

    df = pd.DataFrame(rows)
    df = df.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)
    return df


def main():
    print("[INFO] Membuat dataset percakapan sintetis (seed tetap)...")
    df = build_synthetic_dataset()

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    output_csv = DATASET_DIR / "dataset_raw.csv"
    df.to_csv(output_csv, index=False, encoding="utf-8")

    print(f"[SUCCESS] Dataset berhasil dibuat: {output_csv}")
    print(f"Total baris data: {len(df)}")
    print("\nDistribusi Label:")
    print(df["label"].value_counts())
    print("\nDistribusi Scam Category:")
    print(df[df["label"] == "SCAM"]["scam_category"].value_counts())


if __name__ == "__main__":
    main()
