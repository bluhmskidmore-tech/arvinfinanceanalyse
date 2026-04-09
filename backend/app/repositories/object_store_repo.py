import socket
from dataclasses import dataclass


@dataclass
class ObjectStoreRepository:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str

    def healthcheck(self) -> dict[str, object]:
        host, _, port_str = self.endpoint.partition(":")
        port = int(port_str) if port_str else 9000
        try:
            with socket.create_connection((host, port), timeout=0.2):
                ok = True
        except OSError:
            ok = False
        return {"ok": ok, "endpoint": self.endpoint, "bucket": self.bucket}
