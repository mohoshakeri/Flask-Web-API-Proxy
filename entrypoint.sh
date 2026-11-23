#!/bin/sh
set -eu

NGINX_TIMEOUT="${NGINX_TIMEOUT:-${GUNICORN_TIMEOUT:-60}}"
NGINX_PROXY_CONNECT_TIMEOUT="${NGINX_PROXY_CONNECT_TIMEOUT:-60}"
NGINX_PROXY_SEND_TIMEOUT="${NGINX_PROXY_SEND_TIMEOUT:-${NGINX_TIMEOUT}}"
NGINX_PROXY_READ_TIMEOUT="${NGINX_PROXY_READ_TIMEOUT:-${NGINX_TIMEOUT}}"
NGINX_CLIENT_MAX_BODY_SIZE="${NGINX_CLIENT_MAX_BODY_SIZE:-32m}"
NGINX_CLIENT_BODY_TIMEOUT="${NGINX_CLIENT_BODY_TIMEOUT:-${NGINX_TIMEOUT}}"

export NGINX_PROXY_CONNECT_TIMEOUT
export NGINX_PROXY_SEND_TIMEOUT
export NGINX_PROXY_READ_TIMEOUT
export NGINX_CLIENT_MAX_BODY_SIZE
export NGINX_CLIENT_BODY_TIMEOUT

envsubst '${NGINX_PROXY_CONNECT_TIMEOUT} ${NGINX_PROXY_SEND_TIMEOUT} ${NGINX_PROXY_READ_TIMEOUT} ${NGINX_CLIENT_MAX_BODY_SIZE} ${NGINX_CLIENT_BODY_TIMEOUT}' \
  < /app/nginx/default.conf.template > /etc/nginx/conf.d/default.conf

rm -f /etc/nginx/sites-enabled/default

gunicorn \
  --bind 127.0.0.1:3000 \
  --workers "${GUNICORN_WORKERS}" \
  --timeout "${GUNICORN_TIMEOUT}" \
  --graceful-timeout 30 \
  app:app &
GUNICORN_PID=$!

nginx -t
nginx -g "daemon off;" &
NGINX_PID=$!

shutdown() {
  kill -TERM "${NGINX_PID}" 2>/dev/null || true
  kill -TERM "${GUNICORN_PID}" 2>/dev/null || true
  wait "${NGINX_PID}" 2>/dev/null || true
  wait "${GUNICORN_PID}" 2>/dev/null || true
}

trap shutdown INT TERM

while true; do
  if ! kill -0 "${GUNICORN_PID}" 2>/dev/null; then
    echo "gunicorn exited" >&2
    shutdown
    exit 1
  fi
  if ! kill -0 "${NGINX_PID}" 2>/dev/null; then
    echo "nginx exited" >&2
    shutdown
    exit 1
  fi
  sleep 1
done
