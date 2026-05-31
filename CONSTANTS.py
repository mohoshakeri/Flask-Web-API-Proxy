DEFAULT_REQUEST_TIMEOUT: str = "20"
DEFAULT_TARGET_SCHEME: str = "https"
PRIVATE_TARGETS_ENABLED_VALUE: str = "true"

HOST_HTTP_SCHEME: str = "http"
HOST_HTTPS_SCHEME: str = "https"

SIGN_KEY_ENV: str = "SIGN_KEY"
REQUEST_TIMEOUT_ENV: str = "REQUEST_TIMEOUT"
ALLOW_PRIVATE_TARGETS_ENV: str = "ALLOW_PRIVATE_TARGETS"
TARGET_HOSTS_ENV: str = "TARGET_HOSTS"
IP_ALLOWED_ENV: str = "IP_ALLOWED"

AUTH_HEADER_NAME: str = "PRX-AUTH"
JWT_ALGORITHM: str = "HS256"

ROOT_PATH: str = "/"
HOST_PATH: str = "/<host_id>"
HOST_PROXY_PATH: str = "/<host_id>/<path:path>"
EMPTY_ROUTE_DEFAULT: str = ""

METHOD_GET: str = "GET"
METHOD_POST: str = "POST"
METHOD_PUT: str = "PUT"
METHOD_DELETE: str = "DELETE"
METHOD_PATCH: str = "PATCH"
METHOD_OPTIONS: str = "OPTIONS"
ALLOWED_METHODS: list[str] = [
    METHOD_GET,
    METHOD_POST,
    METHOD_PUT,
    METHOD_DELETE,
    METHOD_PATCH,
    METHOD_OPTIONS,
]

LOCAL_BIND_HOST: str = "0.0.0.0"
LOCAL_BIND_PORT: int = 8000

DEFAULT_HTTPS_PORT: int = 443
DEFAULT_HTTP_PORT: int = 80
FORBIDDEN_STATUS_CODE: int = 403
NOT_FOUND_STATUS_CODE: int = 404
BAD_REQUEST_STATUS_CODE: int = 400
BAD_GATEWAY_STATUS_CODE: int = 502

SIGN_KEY_NOT_FOUND_ERROR: str = "SIGN KEY Not found"
TARGET_HOSTS_FORMAT_ERROR: str = "TARGET_HOSTS must use comma-separated id:hostname entries"
TARGET_HOSTS_NOT_FOUND_ERROR: str = "TARGET_HOSTS Not found"
INVALID_IP_ALLOWED_ERROR: str = "Invalid IP_ALLOWED entry: {}"
UNSUPPORTED_TARGET_SCHEME_ERROR: str = "Only http and https targets are allowed"
INVALID_TARGET_SERVER_ERROR: str = "Invalid targetProxyServer"
TARGET_HOST_NOT_ALLOWED_ERROR: str = "Target host is not allowed"
TARGET_HOST_RESOLUTION_ERROR: str = "Target host could not be resolved"
PRIVATE_TARGET_BLOCKED_ERROR: str = "Private or local target addresses are blocked"
SOURCE_IP_NOT_ALLOWED_ERROR: str = "Source IP is not allowed"
AUTH_HEADER_REQUIRED_ERROR: str = "PRX-AUTH header is required"
JWT_EXPIRED_ERROR: str = "JWT Expired"
JWT_ERROR: str = "JWT Error"
UNKNOWN_TARGET_HOST_ERROR: str = "Unknown target host id"
TARGET_SERVER_ERROR_TEMPLATE: str = "Target Server Error -> {}"

REQUEST_HEADER_BLOCKLIST: set[str] = {
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

RESPONSE_HEADER_BLOCKLIST: set[str] = {
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
