import re
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

LEXICON_PATH = Path(__file__).resolve().parent.parent / "config" / "lexicon.yaml"


def load_lexicon(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Memuat katalog konfigurasi indikator dari berkas lexicon.yaml."""
    target_path = path or LEXICON_PATH
    if not target_path.exists():
        return []
    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data.get("indicators", [])


def _extract_quote(text: str, match_span: tuple[int, int], max_words: int = 15) -> str:
    """Mengekstrak kutipan sekitar pola yang cocok dan membatasinya maksimal 15 kata."""
    words = text.split()
    if len(words) <= max_words:
        return text

    # Jika teks panjang, ambil potongan sekitar match
    start_pos, _ = match_span
    prefix = text[:start_pos]
    word_offset = len(prefix.split()) - 1
    start_idx = max(0, word_offset - 4)
    end_idx = min(len(words), start_idx + max_words)
    return " ".join(words[start_idx:end_idx])


def detect_indicators(
    segments: List[Dict[str, Any]],
    lexicon: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """Mendeteksi indikator penipuan rule-based pada daftar segmen transkrip.
    
    Aturan:
    - Setiap indikator unik hanya dihitung SATU KALI (tidak dihitung ganda).
    - Menandai flagged=True pada segmen terkait.
    - Mengembalikan quote maksimal 15 kata dari transkrip.
    """
    indicators_def = lexicon if lexicon is not None else load_lexicon()
    detected_indicators = []
    seen_codes = set()

    for item in indicators_def:
        code = item["code"]
        label = item["label"]
        weight = item["weight"]
        patterns = item.get("patterns", [])

        # Kompilasi pola regex
        regex_patterns = [re.compile(p, re.IGNORECASE) for p in patterns]

        for seg_idx, segment in enumerate(segments):
            seg_text = segment.get("text", "")
            matched = False
            for rx in regex_patterns:
                match = rx.search(seg_text)
                if match:
                    matched = True
                    segment["flagged"] = True
                    if code not in seen_codes:
                        seen_codes.add(code)
                        quote = _extract_quote(seg_text, match.span(), max_words=15)
                        detected_indicators.append({
                            "code": code,
                            "label": label,
                            "weight": weight,
                            "quote": quote,
                            "segmentIndex": seg_idx,
                        })
                    break
            if code in seen_codes and matched:
                break

    return detected_indicators
