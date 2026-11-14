import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

# Tambahkan path backend ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.models import ModelVersion

METRICS_PATH = Path(__file__).resolve().parent.parent / "ml" / "artifacts" / "v1" / "metrics.json"


def register_model():
    if not METRICS_PATH.exists():
        print(f"[ERROR] File metrik evaluasi tidak ditemukan di {METRICS_PATH}")
        sys.exit(1)

    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    # Pastikan tabel sudah ada
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        model_name = metrics.get("model_name", "savespeech_classifier")
        version = metrics.get("version", "v1.0.0")

        m_version = ModelVersion(
            name=model_name,
            version=version,
            metrics_json=metrics,
            trained_at=datetime.now(timezone.utc),
        )
        db.add(m_version)
        db.commit()
        print(f"[SUCCESS] Model '{model_name}' versi '{version}' berhasil didaftarkan ke tabel model_versions!")
        print(f"ID Record: {m_version.id}")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Gagal mendaftarkan versi model: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    register_model()
