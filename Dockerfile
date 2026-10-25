FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUEST_TIMEOUT=60 \
    GUNICORN_TIMEOUT=60

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

EXPOSE 80

# Gunicorn's default worker timeout is 30s. Long upstream calls (e.g. TTS)
# need REQUEST_TIMEOUT < GUNICORN_TIMEOUT, otherwise the worker is killed and
# clients see a bare HTML 500 Internal Server Error.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:80 --timeout \"${GUNICORN_TIMEOUT}\" --graceful-timeout 30 app:app"]
