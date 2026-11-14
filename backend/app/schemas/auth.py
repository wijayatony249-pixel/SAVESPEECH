import re
import uuid
from typing import Union
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, Field
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    """Schema dasar dengan konfigurasi camelCase untuk kompatibilitas frontend."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class RegisterIn(BaseSchema):
    """Schema input registrasi pengguna."""
    nama: str = Field(..., min_length=2, max_length=100, description="Nama lengkap pengguna")
    email: str = Field(..., description="Alamat email pengguna")
    password: str = Field(..., min_length=8, description="Kata sandi pengguna")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Email harus berupa teks")
        clean = v.strip().lower()
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, clean):
            raise ValueError("Format email tidak valid")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Kata sandi minimal harus 8 karakter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Kata sandi harus memuat minimal satu huruf besar")
        if not re.search(r"[a-z]", v):
            raise ValueError("Kata sandi harus memuat minimal satu huruf kecil")
        if not re.search(r"[0-9]", v):
            raise ValueError("Kata sandi harus memuat minimal satu angka")
        return v


class LoginIn(BaseSchema):
    """Schema input login pengguna."""
    email: str = Field(..., description="Alamat email pengguna")
    password: str = Field(..., min_length=1, description="Kata sandi pengguna")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_and_validate_email(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Email harus berupa teks")
        clean = v.strip().lower()
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, clean):
            raise ValueError("Format email tidak valid")
        return clean


class UserOut(BaseSchema):
    """Schema output profil pengguna."""
    id: str
    nama: str
    email: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v: Union[uuid.UUID, str]) -> str:
        return str(v)


class AuthOut(BaseSchema):
    """Schema respons otentikasi sukses."""
    user: UserOut
    token: str
