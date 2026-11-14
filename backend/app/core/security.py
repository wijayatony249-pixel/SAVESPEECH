"""Security module: hashing password dan verifikasi JWT (diimplementasikan penuh di Phase B3)."""
from typing import Optional


def hash_password(password: str) -> str:
    raise NotImplementedError("Diimplementasikan di Phase B3")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    raise NotImplementedError("Diimplementasikan di Phase B3")


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    raise NotImplementedError("Diimplementasikan di Phase B3")
