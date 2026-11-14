import re


def clean_text(text: str) -> str:
    """Fungsi preprocessing teks yang IDENTIK untuk tahap training dan inferensi runtime.
    
    Langkah:
    1. Mengubah teks ke huruf kecil (lowercase).
    2. Menormalisasi berbagai variasi penulisan OTP menjadi token tunggal 'otp'.
    3. Mengubah angka / deretan digit menjadi token '<num>'.
    4. Menghapus tanda baca berlebih dan filler lisan (e.g., 'ehm', 'uhm', 'ahh').
    5. Menghapus spasi ganda / berlebih.
    
    CATATAN KEAMANAN & AKURASI:
    - JANGAN PERNAH menghapus stopwords! Kata-kata seperti 'jangan', 'segera', 'tidak',
      'peringatan', 'blokir' membawa bobot semantik krusial dalam membedakan penipuan vs panggilan resmi.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Lowercase
    cleaned = text.lower()

    # 2. Normalisasi variasi OTP menjadi token 'otp'
    # contoh: 'o-t-p', 'o t p', 'o.t.p', 'kode otp', 'kode o t p', 'one-time password'
    otp_variations = [
        r"\bone[\s\-_]*time[\s\-_]*password\b",
        r"\bkode[\s\-_]*o[\s\-_]*t[\s\-_]*p\b",
        r"\bo[\s\-_.]+t[\s\-_.]+p\b",
        r"\bkode[\s\-_]*otp\b",
        r"\botp\b",
    ]
    for pattern in otp_variations:
        cleaned = re.sub(pattern, " otp ", cleaned, flags=re.IGNORECASE)

    # Normalisasi PIN / Password / CVV
    cleaned = re.sub(r"\bkode[\s\-_]*pin\b", " pin ", cleaned)
    cleaned = re.sub(r"\bkode[\s\-_]*cvv\b", " cvv ", cleaned)

    # 3. Normalisasi angka numerik menjadi token <num>
    # contoh: '0812345678', 'Rp 500.000', '1234'
    cleaned = re.sub(r"\b(rp|idr)\.?\s*", " rupiah ", cleaned)
    cleaned = re.sub(r"\d+([.,]\d+)*", " <num> ", cleaned)

    # 4. Hapus filler lisan umum dalam bahasa Indonesia
    fillers = [
        r"\b(e+h+m+|u+h+m+|e+e+h+|a+h+h+|o+o+h+)\b",
        r"\b(hmm+|ckck+|aduh+)\b",
    ]
    for filler in fillers:
        cleaned = re.sub(filler, " ", cleaned, flags=re.IGNORECASE)

    # 5. Hapus tanda baca berlebih kecuali token khusus <num>
    # Simpan token <num>
    cleaned = cleaned.replace("<num>", " __NUM_TOKEN__ ")
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = cleaned.replace("__NUM_TOKEN__", "<num>")

    # 6. Rapikan spasi berlebih
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned
