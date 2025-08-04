# syntax=docker/dockerfile:1.4          # ← می‌توانید حذف کنید؛ فقط قابلیت‌های BuildKit پیشرفته را فعال می‌کند
FROM python:3.12-slim                  

# ... (ENV ها همان است)

# --- نصب وابستگی سیستم برای psycopg2 / Pillow و ... ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libpq-dev libjpeg-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# --- requirements ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- کد برنامه ---
WORKDIR /app
COPY . .

# --- کاربر غیرریشه ---
RUN adduser --uid 1000 --disabled-password --gecos "" appuser && \
    chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# برای Production همچنان می‌توانید gunicorn را در docker-compose یا CMD جایگزین کنید

