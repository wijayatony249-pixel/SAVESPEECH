# Panduan Pelabelan Dataset SAVESPEECH (Labeling Guide)

Panduan ini mengatur standar dan kriteria konsistensi pelabelan transkrip percakapan audio untuk model deteksi penipuan impersonasi finansial.

---

## 1. Kriteria Kelas Label

### A. NORMAL (Bukan Penipuan)
- Percakapan sehari-hari (keluarga, teman, rekan kerja).
- Konfirmasi pengantaran barang oleh kurir logistik (tanpa meminta kode rahasia/transfer).
- Telemarketing produk resmi (penawaran asuransi, kartu kredit) di mana pihak penelepon tidak memaksa meminta kata sandi/OTP saat itu juga.
- **Hard Negatives (Sangat Penting)**: Notifikasi resmi dari pihak bank mengenai aktivitas rekening atau transaksi mencurigakan, **namun penelepon secara eksplisit mengingatkan nasabah untuk TIDAK memberitahukan OTP/PIN kepada siapa pun termasuk pihak bank**.

### B. SUSPICIOUS (Mencurigakan)
- Penelepon mengaku dari institusi finansial atau lembaga resmi namun gaya bicaranya tidak wajar atau mendesak tanpa alasan kuat.
- Penelepon menyebutkan ada tagihan, pemblokiran, atau transaksi mencurigakan, namun **belum secara terang-terangan meminta kredensial rahasia (OTP/PIN)**.
- Adanya sedikit unsur ketergesaan (urgency) atau tekanan psikologis ringan.

### C. SCAM (Penipuan Impersonasi Finansial)
Panggilan yang memenuhi salah satu dari skenario penipuan rekayasa sosial (social engineering):
1. **BANK_IMPERSONATION**: Mengaku sebagai petugas keamanan, CS, atau direksi bank, lalu meminta kredensial (OTP, PIN, CVV) dengan dalih membatalkan transaksi liar atau memperbarui data.
2. **E_WALLET_IMPERSONATION**: Mengaku dari platform dompet digital (e-wallet) yang mengklaim akun dibekukan, mendapat undian hadiah, atau perlu upgrade akun ke premium dengan meminta kode verifikasi OTP.
3. **OTP_SCAM**: Secara langsung dan agresif meminta korban menyebutkan atau meneruskan 4-6 digit kode rahasia OTP yang baru saja masuk ke ponsel korban.
4. **TRANSFER_SCAM**: Mengarahkan korban mentransfer sejumlah dana ke "rekening penampungan sementara" (*safe account* / rekening aman) yang diklaim milik bank/kepolisian untuk mengamankan saldo.
5. **ACCOUNT_BLOCKING_SCAM**: Mengancam bahwa rekening atau kartu korban akan diblokir total dalam hitungan menit kecuali korban segera mematuhi instruksi atau mengklik link tertentu.

---

## 2. Katalog 9 Kode Indikator

| Kode Indikator | Label Indonesia | Bobot | Kriteria Pemicu |
| :--- | :--- | :---: | :--- |
| `REQ_OTP` | Permintaan Kode OTP | 30 | Meminta kode verifikasi SMS / WhatsApp yang dikirimkan ke korban. |
| `REQ_CREDENTIAL` | Permintaan PIN / Password / CVV | 30 | Meminta nomor PIN ATM, kata sandi m-banking, CVV/CVC kartu debit/kredit. |
| `TRANSFER_INSTRUCTION`| Instruksi Transfer ("Rekening Aman") | 25 | Menyuruh korban mentransfer uang ke rekening tertentu dengan dalih penyelamatan. |
| `CLAIM_INSTITUTION` | Mengaku Bank / E-Wallet / CS | 15 | Mengklaim representasi resmi dari institusi perbankan, dompet digital, atau layanan konsumen. |
| `BLOCK_THREAT` | Ancaman Pemblokiran Rekening | 15 | Mengancam penutupan, pembekuan, atau pemblokiran fasilitas rekening jika tidak patuh. |
| `APP_LINK_INSTRUCTION`| Instruksi Aplikasi / Link / Remote | 15 | Menyuruh korban mengunduh file APK, mengklik tautan web asing, atau memasang remote access (AnyDesk/TeamViewer). |
| `SUSPICIOUS_TX_INFO` | Informasi Transaksi Mencurigakan | 10 | Memberitahu adanya transaksi bernilai besar, gesek tunai fiktif, atau pinjaman online tanpa seizin korban. |
| `URGENCY` | Unsur Ketergesaan (Mendesak) | 10 | Memaksa korban bertindak saat itu juga ("segera", "dalam 5 menit", "jangan ditutup teleponnya"). |
| `PSYCHOLOGICAL_MANIP` | Manipulasi Psikologis / Intimidasi | 10 | Menakut-nakuti korban dengan konsekuensi hukum, denda, atau pidana jika tidak kooperatif. |

---

## 3. Ketentuan Privasi Data
Seluruh entri dataset sintetis **Wajib Menggunakan Data Fiktif**:
- Nama bank fiktif: Bank Nusantara, Bank Artha Makmur, Bank Dana Sejahtera, PayNusantara, DompetKilat.
- Nama orang fiktif: Budi, Siti, Joko, Hendra, Maya.
- Nomor telepon dan nomor rekening wajib berupa angka generik / token fiktif.
