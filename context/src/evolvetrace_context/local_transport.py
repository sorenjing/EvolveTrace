"""Bounded loopback JSON transport shared by audit and task submission."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .config import ConfigError

DEFAULT_URL = "http://127.0.0.1:8001"
RESPONSE_LIMIT = 2_097_152


class LocalHTTPError(ConfigError):
    def __init__(self, code: int):
        self.code = code
        super().__init__(f"local service returned HTTP {code}")


class LocalServiceUnavailable(ConfigError):
    pass


def _origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise ConfigError("EvolveTrace URL must use a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("EvolveTrace URL must not contain credentials, query, or fragment")
    return value.rstrip("/")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ConfigError("local service redirects are not allowed")


def request_json(origin: str, method: str, path: str, payload: dict | None = None) -> dict:
    request = Request(_origin(origin) + "/api" + path, method=method,
                      data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                      headers={"Accept": "application/json", "Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=3) as response:
            body = response.read(RESPONSE_LIMIT + 1)
    except HTTPError as exc:
        raise LocalHTTPError(exc.code) from exc
    except (URLError, OSError, TimeoutError) as exc:
        raise LocalServiceUnavailable("local service unavailable") from exc
    if len(body) > RESPONSE_LIMIT:
        raise ConfigError("local response exceeds size limit")
    try:
        result = json.loads(body)
    except ValueError as exc:
        raise ConfigError("invalid local JSON response") from exc
    if not isinstance(result, dict):
        raise ConfigError("invalid local JSON response")
    return result
