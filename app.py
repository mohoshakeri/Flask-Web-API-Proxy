import ipaddress
import os
import re
import socket
from urllib.parse import SplitResult, quote, urlsplit

import jwt
import requests
from dotenv import load_dotenv
from flask import Flask, Response, request

from CONSTANTS import ALLOW_PRIVATE_TARGETS_ENV
from CONSTANTS import ALLOWED_METHODS
from CONSTANTS import AUTH_HEADER_NAME
from CONSTANTS import BAD_GATEWAY_STATUS_CODE
from CONSTANTS import BAD_REQUEST_STATUS_CODE
from CONSTANTS import DEFAULT_HTTP_PORT
from CONSTANTS import DEFAULT_HTTPS_PORT
from CONSTANTS import DEFAULT_REQUEST_TIMEOUT
from CONSTANTS import DEFAULT_TARGET_SCHEME
from CONSTANTS import EMPTY_ROUTE_DEFAULT
from CONSTANTS import FORBIDDEN_STATUS_CODE
from CONSTANTS import HOST_HTTP_SCHEME
from CONSTANTS import HOST_HTTPS_SCHEME
from CONSTANTS import HOST_PATH
from CONSTANTS import HOST_PROXY_PATH
from CONSTANTS import INVALID_IP_ALLOWED_ERROR
from CONSTANTS import INVALID_TARGET_SERVER_ERROR
from CONSTANTS import IP_ALLOWED_ENV
from CONSTANTS import JWT_ALGORITHM
from CONSTANTS import JWT_ERROR
from CONSTANTS import JWT_EXPIRED_ERROR
from CONSTANTS import LOCAL_BIND_HOST
from CONSTANTS import LOCAL_BIND_PORT
from CONSTANTS import NOT_FOUND_STATUS_CODE
from CONSTANTS import PRIVATE_TARGET_BLOCKED_ERROR
from CONSTANTS import PRIVATE_TARGETS_ENABLED_VALUE
from CONSTANTS import REQUEST_HEADER_BLOCKLIST
from CONSTANTS import REQUEST_TIMEOUT_ENV
from CONSTANTS import RESPONSE_HEADER_BLOCKLIST
from CONSTANTS import ROOT_PATH
from CONSTANTS import SIGN_KEY_ENV
from CONSTANTS import SIGN_KEY_NOT_FOUND_ERROR
from CONSTANTS import SOURCE_IP_NOT_ALLOWED_ERROR
from CONSTANTS import TARGET_HOST_NOT_ALLOWED_ERROR
from CONSTANTS import TARGET_HOST_RESOLUTION_ERROR
from CONSTANTS import TARGET_HOSTS_ENV
from CONSTANTS import TARGET_HOSTS_FORMAT_ERROR
from CONSTANTS import TARGET_HOSTS_NOT_FOUND_ERROR
from CONSTANTS import TARGET_SERVER_ERROR_TEMPLATE
from CONSTANTS import UNKNOWN_TARGET_HOST_ERROR
from CONSTANTS import UNSUPPORTED_TARGET_SCHEME_ERROR

app: Flask = Flask(__name__)
app.debug = False

load_dotenv(override=True)
SIGN_KEY: str | None = os.getenv(SIGN_KEY_ENV)
REQUEST_TIMEOUT: float = float(os.getenv(REQUEST_TIMEOUT_ENV, DEFAULT_REQUEST_TIMEOUT))
ALLOW_PRIVATE_TARGETS: bool = os.getenv(ALLOW_PRIVATE_TARGETS_ENV, "").lower() == PRIVATE_TARGETS_ENABLED_VALUE
TARGET_HOSTS_RAW: str = os.getenv(TARGET_HOSTS_ENV, "")
IP_ALLOWED_RAW: str = os.getenv(IP_ALLOWED_ENV, "")

if SIGN_KEY is None:
    raise ValueError(SIGN_KEY_NOT_FOUND_ERROR)


def _parse_target_hosts(raw_value: str) -> dict[str, str]:
    target_hosts: dict[str, str] = {}
    for raw_item in raw_value.split(","):
        item: str = raw_item.strip()
        if not item:
            continue

        host_id: str
        separator: str
        host_value: str
        host_id, separator, host_value = item.partition(":")
        if not separator or not host_id.strip() or not host_value.strip():
            raise ValueError(TARGET_HOSTS_FORMAT_ERROR)

        normalized_id: str = host_id.strip().lower()
        normalized_target: str = host_value.strip()
        if "://" not in normalized_target:
            normalized_target = "{}://{}".format(DEFAULT_TARGET_SCHEME, normalized_target)

        target_hosts[normalized_id] = normalized_target.rstrip("/")

    if not target_hosts:
        raise ValueError(TARGET_HOSTS_NOT_FOUND_ERROR)

    return target_hosts


def _parse_allowed_networks(raw_value: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw_item in raw_value.split(","):
        item: str = raw_item.strip()
        if not item:
            continue
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(item)
                networks.append(ipaddress.ip_network("{}/{}".format(ip_obj, ip_obj.max_prefixlen), strict=False))
        except ValueError as exc:
            raise ValueError(INVALID_IP_ALLOWED_ERROR.format(item)) from exc
    return networks


def _extract_allowed_target_hosts(target_hosts: dict[str, str]) -> set[str]:
    allowed_hosts: set[str] = set()
    for target in target_hosts.values():
        parsed_target: SplitResult = urlsplit(target)
        hostname: str | None = parsed_target.hostname
        if hostname:
            allowed_hosts.add(hostname.lower())
    return allowed_hosts


TARGET_HOSTS: dict[str, str] = _parse_target_hosts(TARGET_HOSTS_RAW)
ALLOWED_TARGET_HOSTS: set[str] = _extract_allowed_target_hosts(TARGET_HOSTS)
ALLOWED_IP_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = _parse_allowed_networks(IP_ALLOWED_RAW)


def _is_public_ip(ip_value: str) -> bool:
    ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(ip_value)
    return not (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _validate_target_url(target_base: str) -> tuple[bool, str | None]:
    parsed_target = urlsplit(target_base)
    if parsed_target.scheme not in {HOST_HTTP_SCHEME, HOST_HTTPS_SCHEME}:
        return False, UNSUPPORTED_TARGET_SCHEME_ERROR

    if not parsed_target.netloc or parsed_target.username or parsed_target.password:
        return False, INVALID_TARGET_SERVER_ERROR

    hostname: str | None = parsed_target.hostname
    if not hostname:
        return False, INVALID_TARGET_SERVER_ERROR

    normalized_host: str = hostname.lower()
    if ALLOWED_TARGET_HOSTS and normalized_host not in ALLOWED_TARGET_HOSTS:
        return False, TARGET_HOST_NOT_ALLOWED_ERROR

    if ALLOW_PRIVATE_TARGETS:
        return True, None

    try:
        port: int = parsed_target.port or (
            DEFAULT_HTTPS_PORT if parsed_target.scheme == HOST_HTTPS_SCHEME else DEFAULT_HTTP_PORT
        )
        address_info: list[
            tuple[
                socket.AddressFamily,
                socket.SocketKind,
                int,
                str,
                tuple[str, int] | tuple[str, int, int, int],
            ]
        ] = socket.getaddrinfo(hostname, port)
    except socket.gaierror:
        return False, TARGET_HOST_RESOLUTION_ERROR

    resolved_ips: set[str] = {item[4][0] for item in address_info}
    if not resolved_ips or any(not _is_public_ip(ip_value) for ip_value in resolved_ips):
        return False, PRIVATE_TARGET_BLOCKED_ERROR

    return True, None


def _build_target_url(target_base: str, path: str) -> str:
    base: str = target_base.rstrip("/")
    if not path:
        return base
    # urljoin collapses "//" inside paths (e.g. Search Console siteUrl
    # ".../sites/https://example.com/" → ".../sites/https:/example.com/").
    encoded_path: str = _encode_target_path(path.lstrip("/"))
    return "{}/{}".format(base, encoded_path)


def _encode_target_path(path: str) -> str:
    """Keep Embedded Absolute Urls As A Single Encoded Path Segment."""
    def _encode_site_url(match: re.Match[str]) -> str:
        return quote(match.group(0), safe="")

    return re.sub(r"https?://[^/]+/?", _encode_site_url, path)


def _filtered_query_params() -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in request.args.items(multi=True)
    ]


def _filtered_request_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        normalized_key: str = key.lower()
        if normalized_key in REQUEST_HEADER_BLOCKLIST or normalized_key == AUTH_HEADER_NAME.lower():
            continue
        headers[key] = value
    return headers


def _is_ip_allowed(remote_ip: str) -> bool:
    if not ALLOWED_IP_NETWORKS:
        return True
    try:
        ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return any(ip_obj in network for network in ALLOWED_IP_NETWORKS)


def _decode_auth_token(jwt_token: str) -> tuple[bool, str | None]:
    try:
        jwt.decode(jwt_token, SIGN_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return False, JWT_EXPIRED_ERROR
    except jwt.InvalidTokenError:
        return False, JWT_ERROR
    return True, None


def _send_target_request(target_url: str) -> requests.Response:
    return requests.request(
        method=request.method,
        url=target_url,
        params=_filtered_query_params(),
        headers=_filtered_request_headers(),
        data=request.get_data(),
        allow_redirects=False,
        timeout=REQUEST_TIMEOUT,
    )


def _build_proxy_response(target_response: requests.Response) -> Response:
    proxy_response: Response = Response(target_response.content, status=target_response.status_code)
    for name, value in target_response.headers.items():
        if name.lower() not in RESPONSE_HEADER_BLOCKLIST:
            proxy_response.headers[name] = value
    return proxy_response


@app.route(
    ROOT_PATH,
    defaults={"host_id": EMPTY_ROUTE_DEFAULT, "path": EMPTY_ROUTE_DEFAULT},
    methods=ALLOWED_METHODS,
)
@app.route(HOST_PATH, defaults={"path": EMPTY_ROUTE_DEFAULT}, methods=ALLOWED_METHODS)
@app.route(HOST_PROXY_PATH, methods=ALLOWED_METHODS)
def proxy(host_id: str, path: str) -> Response | tuple[str, int]:
    remote_ip: str = request.remote_addr or ""
    if not _is_ip_allowed(remote_ip):
        return SOURCE_IP_NOT_ALLOWED_ERROR, FORBIDDEN_STATUS_CODE

    jwt_token: str | None = request.headers.get(AUTH_HEADER_NAME)
    if not jwt_token:
        return AUTH_HEADER_REQUIRED_ERROR, FORBIDDEN_STATUS_CODE

    is_valid_token: bool
    auth_error: str | None
    is_valid_token, auth_error = _decode_auth_token(jwt_token)
    if not is_valid_token and auth_error is not None:
        return auth_error, FORBIDDEN_STATUS_CODE

    target_base: str | None = TARGET_HOSTS.get(host_id.lower())
    if not target_base:
        return UNKNOWN_TARGET_HOST_ERROR, NOT_FOUND_STATUS_CODE

    is_valid_target: bool
    validation_error: str | None
    is_valid_target, validation_error = _validate_target_url(target_base)
    if not is_valid_target and validation_error is not None:
        return validation_error, BAD_REQUEST_STATUS_CODE

    try:
        target_response: requests.Response = _send_target_request(_build_target_url(target_base, path))
    except requests.exceptions.RequestException as exc:
        return TARGET_SERVER_ERROR_TEMPLATE.format(str(exc)), BAD_GATEWAY_STATUS_CODE

    return _build_proxy_response(target_response)


if __name__ == "__main__":
    app.run(host=LOCAL_BIND_HOST, port=LOCAL_BIND_PORT, debug=False, use_reloader=False)
