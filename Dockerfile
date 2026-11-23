FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUEST_TIMEOUT=60 \
    GUNICORN_TIMEOUT=60 \
    GUNICORN_WORKERS=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 80

# Sync workers: one in-flight upstream call per worker. Raise GUNICORN_WORKERS
# to match expected concurrent long calls (e.g. TTS). Keep
# GUNICORN_TIMEOUT >= REQUEST_TIMEOUT or Gunicorn kills the worker mid-request.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:80 --workers \"${GUNICORN_WORKERS}\" --timeout \"${GUNICORN_TIMEOUT}\" --graceful-timeout 30 app:app"]
