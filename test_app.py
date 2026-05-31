import importlib
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any

import jwt
import pytest
from flask.testing import FlaskClient

SIGN_KEY: str = "test-secret"
TARGET_HOSTS: str = "example:https://example.com,api:api.example.com"
PRIVATE_TARGETS_ENABLED: str = "true"
AUTH_HEADER_NAME: str = "PRX-AUTH"
JWT_ALGORITHM: str = "HS256"
SUCCESS_STATUS_CODE: int = 201
FORBIDDEN_STATUS_CODE: int = 403
NOT_FOUND_STATUS_CODE: int = 404
BAD_GATEWAY_STATUS_CODE: int = 502


@dataclass
class FakeTargetResponse:
    content: bytes
    status_code: int
    headers: dict[str, str]


def _load_app(monkeypatch: pytest.MonkeyPatch, ip_allowed: str = "") -> ModuleType:
    monkeypatch.setenv("SIGN_KEY", SIGN_KEY)
    monkeypatch.setenv("TARGET_HOSTS", TARGET_HOSTS)
    monkeypatch.setenv("ALLOW_PRIVATE_TARGETS", PRIVATE_TARGETS_ENABLED)
    monkeypatch.setenv("IP_ALLOWED", ip_allowed)
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def _client(app_module: ModuleType) -> FlaskClient:
    return app_module.app.test_client()


def _auth_headers() -> dict[str, str]:
    token: str = jwt.encode({"sub": "test-user"}, SIGN_KEY, algorithm=JWT_ALGORITHM)
    return {AUTH_HEADER_NAME: token}


def test_parse_target_hosts_adds_default_https(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)

    parsed_hosts: dict[str, str] = app_module._parse_target_hosts("one:example.org,two:http://api.example.org")

    assert parsed_hosts == {
        "one": "https://example.org",
        "two": "http://api.example.org",
    }


def test_parse_target_hosts_rejects_invalid_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)

    with pytest.raises(ValueError, match="TARGET_HOSTS must use comma-separated"):
        app_module._parse_target_hosts("broken-entry")


def test_request_without_auth_is_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)
    client: FlaskClient = _client(app_module)

    response = client.get("/example/v1/models")

    assert response.status_code == FORBIDDEN_STATUS_CODE
    assert response.get_data(as_text=True) == "PRX-AUTH header is required"


def test_unknown_host_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)
    client: FlaskClient = _client(app_module)

    response = client.get("/missing/v1/models", headers=_auth_headers())

    assert response.status_code == NOT_FOUND_STATUS_CODE
    assert response.get_data(as_text=True) == "Unknown target host id"


def test_source_ip_allowlist_blocks_unlisted_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch, ip_allowed="203.0.113.10")
    client: FlaskClient = _client(app_module)

    response = client.get("/example/v1/models", headers=_auth_headers())

    assert response.status_code == FORBIDDEN_STATUS_CODE
    assert response.get_data(as_text=True) == "Source IP is not allowed"


def test_proxy_forwards_request_and_filters_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)
    client: FlaskClient = _client(app_module)
    captured_request: dict[str, Any] = {}

    def fake_request(**kwargs: Any) -> FakeTargetResponse:
        captured_request.update(kwargs)
        return FakeTargetResponse(
            content=b'{"ok":true}',
            status_code=SUCCESS_STATUS_CODE,
            headers={
                "Content-Type": "application/json",
                "Content-Length": "999",
                "X-Upstream": "yes",
            },
        )

    monkeypatch.setattr(app_module.requests, "request", fake_request)

    response = client.post(
        "/example/v1/items?tag=one&tag=two",
        data=b"payload",
        headers={
            **_auth_headers(),
            "X-Custom": "client-value",
            "X-Forwarded-For": "198.51.100.7",
        },
    )

    assert response.status_code == SUCCESS_STATUS_CODE
    assert response.get_data() == b'{"ok":true}'
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["X-Upstream"] == "yes"
    assert captured_request["method"] == "POST"
    assert captured_request["url"] == "https://example.com/v1/items"
    assert captured_request["params"] == [("tag", "one"), ("tag", "two")]
    assert captured_request["data"] == b"payload"
    assert captured_request["allow_redirects"] is False
    assert captured_request["timeout"] == app_module.REQUEST_TIMEOUT
    assert captured_request["headers"]["X-Custom"] == "client-value"
    assert AUTH_HEADER_NAME not in captured_request["headers"]
    assert "X-Forwarded-For" not in captured_request["headers"]


def test_target_request_errors_return_bad_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    app_module: ModuleType = _load_app(monkeypatch)
    client: FlaskClient = _client(app_module)

    def fake_request(**kwargs: Any) -> FakeTargetResponse:
        raise app_module.requests.exceptions.Timeout("slow upstream")

    monkeypatch.setattr(app_module.requests, "request", fake_request)

    response = client.get("/example/v1/models", headers=_auth_headers())

    assert response.status_code == BAD_GATEWAY_STATUS_CODE
    assert response.get_data(as_text=True) == "Target Server Error -> slow upstream"
