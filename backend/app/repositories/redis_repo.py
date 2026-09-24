import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class RedisRepository:
    dsn: str

    def healthcheck(self) -> dict[str, object]:
        parsed = urlparse(self.dsn)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        try:
            with socket.create_connection((host, port), timeout=0.2):
                ok = True
        except OSError:
            ok = False
        return {"ok": ok, "dsn": _mask_dsn(self.dsn)}


def _mask_dsn(dsn: str) -> str:
    # Same masking rules as postgres_repo._mask_dsn: the healthcheck payload is
    # exposed by the unauthenticated readiness endpoint and must never echo
    # plaintext credentials (redis://:password@host style DSNs).
    parsed = urlparse(dsn)
    if not parsed.scheme or not parsed.hostname:
        return dsn

    username = parsed.username or ""
    password = parsed.password
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    credentials = username
    if password is not None:
        credentials = f"{credentials}:***" if credentials else "***"
    if credentials:
        netloc = f"{credentials}@{hostname}{port}"
    else:
        netloc = f"{hostname}{port}"
    return parsed._replace(netloc=netloc).geturl()
