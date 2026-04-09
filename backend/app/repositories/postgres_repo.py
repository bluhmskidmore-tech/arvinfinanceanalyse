import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class PostgresRepository:
    dsn: str

    def healthcheck(self) -> dict[str, object]:
        parsed = urlparse(self.dsn)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        try:
            with socket.create_connection((host, port), timeout=0.2):
                ok = True
        except OSError:
            ok = False
        return {"ok": ok, "dsn": self.dsn}
