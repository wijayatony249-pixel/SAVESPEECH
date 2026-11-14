from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path


class Settings(BaseSettings):
    """Konfigurasi aplikasi SAVESPEECH dari environment variables."""

    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/savespeech_db"
    JWT_SECRET: str = "dev_secret_key_change_in_production_min_32_chars_12345"
    JWT_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    MAX_UPLOAD_MB: int = 25
    MAX_DURATION_SEC: int = 600
    TEMP_DIR: str = "temp_audio"

    # Konfigurasi Speech-to-Text faster-whisper
    WHISPER_MODEL: str = "small"
    WHISPER_COMPUTE: str = "int8"
    WHISPER_DEVICE: str = "cpu"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError("Format CORS_ORIGINS tidak valid")

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret_length(cls, v: str, info) -> str:
        # JWT_SECRET wajib minimal 32 karakter di luar mode dev
        env = info.data.get("APP_ENV", "development")
        if env != "development" and len(v) < 32:
            raise ValueError("JWT_SECRET wajib memiliki panjang minimal 32 karakter di luar mode development")
        return v

    @property
    def temp_dir_path(self) -> Path:
        """Mengembalikan objek Path untuk TEMP_DIR dan memastikan foldernya ada."""
        p = Path(self.TEMP_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
