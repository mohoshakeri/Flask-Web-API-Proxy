FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUEST_TIMEOUT=60 \
    GUNICORN_TIMEOUT=60 \
    GUNICORN_WORKERS=1 \
    NGINX_TIMEOUT=60 \
    NGINX_PROXY_CONNECT_TIMEOUT=60 \
    NGINX_CLIENT_MAX_BODY_SIZE=32m

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 80

# Public port 80 is nginx. Gunicorn listens on 127.0.0.1:3000.
# Keep GUNICORN_TIMEOUT / NGINX_TIMEOUT >= REQUEST_TIMEOUT for long TTS.
ENTRYPOINT ["/app/entrypoint.sh"]
