import os
import sys
import argparse
from passlib.context import CryptContext

# Tambahkan direktori root backend ke sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_admin(name: str, email: str, password: str) -> None:
    """Membuat pengguna dengan role admin tanpa meng-hardcode password."""
    email_clean = email.strip().lower()
    if not name or not email_clean or not password:
        print("[ERROR] Nama, email, dan password wajib diisi.")
        sys.exit(1)

    if len(password) < 8:
        print("[ERROR] Password admin minimal 8 karakter.")
        sys.exit(1)

    # Pastikan tabel sudah ada
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == email_clean).first()
        if existing_user:
            print(f"[INFO] Pengguna dengan email '{email_clean}' sudah ada. Memperbarui ke role admin...")
            existing_user.role = "admin"
            existing_user.nama = name
            existing_user.password_hash = pwd_context.hash(password)
            db.commit()
            print(f"[SUCCESS] Pengguna '{email_clean}' berhasil diperbarui sebagai admin.")
            return

        hashed = pwd_context.hash(password)
        admin_user = User(
            nama=name,
            email=email_clean,
            password_hash=hashed,
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        print(f"[SUCCESS] User admin '{email_clean}' berhasil dibuat (ID: {admin_user.id}).")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Gagal membuat user admin: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Script pembuat user admin SAVESPEECH.")
    parser.add_argument("--name", default=os.getenv("ADMIN_NAME", "Administrator SAVESPEECH"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", "admin@savespeech.id"))
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", None))
    args = parser.parse_args()

    password = args.password
    if not password:
        password = os.getenv("ADMIN_PASSWORD")
    if not password:
        import getpass
        password = getpass.getpass("Masukkan password admin: ")

    create_admin(args.name, args.email, password)


if __name__ == "__main__":
    main()
