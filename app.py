import ipaddress
import os
import socket
from urllib.parse import urljoin, urlsplit

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, Response, request

app = Flask(__name__)
app.debug = False

load_dotenv(override=True)
SIGN_KEY = os.getenv("SIGN_KEY")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "20"))
ALLOW_PRIVATE_TARGETS = os.getenv("ALLOW_PRIVATE_TARGETS", "").lower() == "true"
TARGET_HOSTS_RAW = os.getenv("TARGET_HOSTS", "")
IP_ALLOWED_RAW = os.getenv("IP_ALLOWED", "")

REQUEST_HEADER_BLOCKLIST = {
    "accept-encoding",
    "connection",
    "content-length",
    "forwarded",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "via",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-real-ip",
    "true-client-ip",
    "cf-connecting-ip",
    "cf-ray",
    "cdn-loop",
}

RESPONSE_HEADER_BLOCKLIST = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

if SIGN_KEY is None:
    raise ValueError("SIGN KEY Not found")


def _parse_target_hosts(raw_value):
    target_hosts = {}
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue

        host_id, separator, host_value = item.partition(":")
        if not separator or not host_id.strip() or not host_value.strip():
            raise ValueError("TARGET_HOSTS must use comma-separated id:hostname entries")

        normalized_id = host_id.strip().lower()
        normalized_target = host_value.strip()
        if "://" not in normalized_target:
            normalized_target = f"https://{normalized_target}"

        target_hosts[normalized_id] = normalized_target.rstrip("/")

    if not target_hosts:
        raise ValueError("TARGET_HOSTS Not found")

    return target_hosts


def _parse_allowed_networks(raw_value):
    networks = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                ip_obj = ipaddress.ip_address(item)
                networks.append(ipaddress.ip_network(f"{ip_obj}/{ip_obj.max_prefixlen}", strict=False))
        except ValueError as exc:
            raise ValueError(f"Invalid IP_ALLOWED entry: {item}") from exc
    return networks


TARGET_HOSTS = _parse_target_hosts(TARGET_HOSTS_RAW)
ALLOWED_TARGET_HOSTS = {urlsplit(target).hostname.lower() for target in TARGET_HOSTS.values() if urlsplit(target).hostname}
ALLOWED_IP_NETWORKS = _parse_allowed_networks(IP_ALLOWED_RAW)


def _is_public_ip(ip_value):
    ip_obj = ipaddress.ip_address(ip_value)
    return not (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _validate_target_url(target_base):
    parsed = urlsplit(target_base)
    if parsed.scheme not in {"http", "https"}:
        return None, "Only http and https targets are allowed"

    if not parsed.netloc or parsed.username or parsed.password:
        return None, "Invalid targetProxyServer"

    hostname = parsed.hostname
    if not hostname:
        return None, "Invalid targetProxyServer"

    normalized_host = hostname.lower()
    if ALLOWED_TARGET_HOSTS and normalized_host not in ALLOWED_TARGET_HOSTS:
        return None, "Target host is not allowed"

    if not ALLOW_PRIVATE_TARGETS:
        try:
            addrinfo = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror:
            return None, "Target host could not be resolved"

        resolved_ips = {item[4][0] for item in addrinfo}
        if not resolved_ips or any(not _is_public_ip(ip_value) for ip_value in resolved_ips):
            return None, "Private or local target addresses are blocked"

    return parsed, None


def _build_target_url(target_base, path):
    base = target_base if target_base.endswith("/") else f"{target_base}/"
    return urljoin(base, path) if path else target_base


def _filtered_query_params():
    return [
        (key, value)
        for key, value in request.args.items(multi=True)
    ]


def _filtered_request_headers():
    headers = {}
    for key, value in request.headers.items():
        if key.lower() in REQUEST_HEADER_BLOCKLIST or key.lower() == "prx-auth":
            continue
        headers[key] = value
    return headers


def _is_ip_allowed(remote_ip):
    if not ALLOWED_IP_NETWORKS:
        return True
    try:
        ip_obj = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return any(ip_obj in network for network in ALLOWED_IP_NETWORKS)


@app.route(
    "/",
    defaults={"host_id": "", "path": ""},
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
@app.route("/<host_id>", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@app.route("/<host_id>/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def proxy(host_id, path):
    remote_ip = request.remote_addr or ""
    if not _is_ip_allowed(remote_ip):
        return "Source IP is not allowed", 403

    # Auth
    jwt_token = request.headers.get("PRX-AUTH")
    if not jwt_token:
        return "PRX-AUTH header is required", 403

    try:
        jwt.decode(jwt_token, SIGN_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return "JWT Expired", 403
    except jwt.InvalidTokenError:
        return "JWT Error", 403

    # Target
    target_base = TARGET_HOSTS.get(host_id.lower())
    if not target_base:
        return "Unknown target host id", 404

    _, validation_error = _validate_target_url(target_base)
    if validation_error:
        return validation_error, 400

    # Clean Path
    target_url = _build_target_url(target_base, path)

    # GET Params
    params = _filtered_query_params()

    # Headers
    headers = _filtered_request_headers()

    # Body
    data = request.get_data()

    try:
        # Request
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=params,
            headers=headers,
            data=data,
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        return f"Target Server Error -> {str(e)}", 502

    # Response
    response = Response(resp.content, status=resp.status_code)

    # Response Headers
    for name, value in resp.headers.items():
        if name.lower() not in RESPONSE_HEADER_BLOCKLIST:
            response.headers[name] = value

    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
