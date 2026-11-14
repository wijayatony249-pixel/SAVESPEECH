FROM python:3.11-slim

# Pasang dependensi sistem: ffmpeg untuk decoding audio dan curl untuk healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Buat pengguna non-root demi keamanan (Least Privilege Principle)
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1001 appuser

WORKDIR /app

# Salin requirements dan pasang pustaka Python
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Salin kode aplikasi backend
COPY . /app

# Buat direktori temporer audio dan cache model dengan izin yang sesuai untuk appuser
RUN mkdir -p /tmp/savespeech /root/.cache/huggingface \
    && chown -R appuser:appgroup /app /tmp/savespeech

# Ganti ke pengguna non-root
USER appuser

# Expose port FastAPI
EXPOSE 8000

# Healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Entrypoint: Jalankan migrasi Alembic terlebih dahulu, kemudian start Uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
