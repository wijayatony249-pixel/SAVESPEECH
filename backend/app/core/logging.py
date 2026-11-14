import logging
import re
from typing import Any


SENSITIVE_PATTERNS = [
    (re.compile(r'(password|kata_sandi|passwd)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE), r'\1=***'),
    (re.compile(r'(token|access_token|refresh_token)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE), r'\1=***'),
    (re.compile(r'(otp|kode_otp)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE), r'\1=***'),
    (re.compile(r'(transcript|transkrip)\s*[:=]\s*["\']?([^"\'\n]+)["\']?', re.IGNORECASE), r'\1=[REDACTED_TRANSCRIPT]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), r'Bearer ***'),
]


class SensitiveDataFilter(logging.Filter):
    """Filter untuk menyamarkan informasi rahasia dan sensitif dari log."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)

        if record.args:
            if isinstance(record.args, dict):
                redacted_args = {}
                for k, v in record.args.items():
                    k_lower = str(k).lower()
                    if any(s in k_lower for s in ("password", "token", "otp", "transcript", "transkrip")):
                        redacted_args[k] = "***"
                    else:
                        redacted_args[k] = v
                record.args = redacted_args
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_value(arg) for arg in record.args)

        return True

    def _redact_value(self, val: Any) -> Any:
        if isinstance(val, str):
            for pattern, replacement in SENSITIVE_PATTERNS:
                val = pattern.sub(replacement, val)
            return val
        return val


def setup_logging(level: str = "INFO") -> None:
    """Mengonfigurasi logging terstruktur dan memasang filter data sensitif."""
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Hapus handler default agar tidak duplikat
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Pastikan uvicorn logger juga memakai filter
    for uvicorn_log in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        u_logger = logging.getLogger(uvicorn_log)
        u_logger.addFilter(SensitiveDataFilter())
