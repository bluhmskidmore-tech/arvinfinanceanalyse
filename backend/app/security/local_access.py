"""The opted-in single-user API trusts the local machine, never a proxy identity."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def is_loopback_address(value: object) -> bool:
    text = str(value or "").strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def is_local_hostname(value: object) -> bool:
    return str(value or "").lower() == "localhost" or is_loopback_address(value)


def local_origin(value: str, *, allow_path: bool = False) -> str | None:
    if any(character.isspace() or ord(character) < 32 or character == "\\" for character in value):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not is_local_hostname(parsed.hostname)
            or parsed.username is not None or parsed.password is not None
            or parsed.netloc.endswith(":")
            or (not allow_path and (parsed.path or parsed.query or parsed.fragment))
        ):
            return None
        port = parsed.port
        if port == 0:
            return None
        hostname = str(parsed.hostname).lower()
        authority = f"[{hostname}]" if ":" in hostname else hostname
        default_port = 80 if parsed.scheme == "http" else 443
        if port is not None and port != default_port:
            authority += f":{port}"
        return f"{parsed.scheme}://{authority}"
    except ValueError:
        return None


def _local_host(value: str, *, server_port: int, scheme: str) -> bool:
    if value.endswith(":") or any(character in value for character in "@/\\?#, \t\r\n"):
        return False
    try:
        parsed = urlsplit(f"//{value}")
        port = parsed.port
        if port == 0:
            return False
        port = port if port is not None else (443 if scheme == "https" else 80)
        return is_local_hostname(parsed.hostname) and port == server_port
    except ValueError:
        return False


class LocalDevelopmentAccessMiddleware:
    """Reject non-local development requests before CORS, data reads or actions.

    Non-development deployments retain their existing gateway/CORS contracts.
    The existing Vite proxy changes Host to the API and does not enable xfwd.
    """

    def __init__(self, app: ASGIApp, *, environment: str, local_only_api: bool) -> None:
        self.app = app
        self.enabled = local_only_api and environment.strip().lower() == "development"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        server = scope.get("server")
        headers: dict[bytes, list[bytes]] = {}
        for name, value in scope.get("headers", []):
            headers.setdefault(name.lower(), []).append(value)
        proxy_identity = any(
            name in {b"forwarded", b"x-real-ip"} or name.startswith(b"x-forwarded-")
            for name in headers
        )
        allowed = (
            bool(client) and is_loopback_address(client[0])
            and bool(server) and is_loopback_address(server[0])
            and not proxy_identity
            and len(headers.get(b"host", [])) == 1
        )
        if allowed:
            host = headers[b"host"][0].decode("latin-1")
            allowed = _local_host(host, server_port=server[1], scheme=str(scope.get("scheme") or "http"))
        for name in (b"origin", b"referer"):
            values = headers.get(name, [])
            if len(values) > 1:
                allowed = False
            if values:
                value = values[0].decode("latin-1")
                origin = local_origin(value, allow_path=name == b"referer")
                if origin is None:
                    allowed = False
        fetch_sites = headers.get(b"sec-fetch-site", [])
        if len(fetch_sites) > 1:
            allowed = False
        if (
            any(value.lower() == b"cross-site" for value in fetch_sites)
            and b"origin" not in headers and b"referer" not in headers
        ):
            allowed = False
        if not allowed:
            await JSONResponse(status_code=403, content={"detail": "Development API access is restricted to trusted local requests."})(scope, receive, send)
            return
        await self.app(scope, receive, send)
