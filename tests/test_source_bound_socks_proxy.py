from __future__ import annotations

import socket
import socketserver
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from backend.app.network.source_bound_socks_proxy import source_bound_socks_proxy


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("socket closed before the expected response arrived")
        chunks.extend(chunk)
    return bytes(chunks)


class _EchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        peer_ip = self.client_address[0].encode("ascii")
        self.request.sendall(peer_ip + b"|")
        while data := self.request.recv(65536):
            self.request.sendall(data)


class _EchoServer(socketserver.ThreadingTCPServer):
    address_family = socket.AF_INET
    allow_reuse_address = True
    daemon_threads = True


@contextmanager
def _echo_server() -> Iterator[tuple[str, int]]:
    server = _EchoServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _open_socks_connection(
    proxy_address: tuple[str, int],
    destination: str,
    destination_port: int,
    *,
    address_type: int,
    command: int = 1,
) -> tuple[socket.socket, int]:
    client = socket.create_connection(proxy_address, timeout=2)
    client.settimeout(2)
    client.sendall(b"\x05\x01\x00")
    assert _recv_exact(client, 2) == b"\x05\x00"

    if address_type == 1:
        encoded_address = socket.inet_aton(destination)
    elif address_type == 3:
        encoded_host = destination.encode("idna")
        encoded_address = bytes([len(encoded_host)]) + encoded_host
    else:
        raise AssertionError(f"unsupported test address type: {address_type}")

    client.sendall(
        b"\x05"
        + bytes([command])
        + b"\x00"
        + bytes([address_type])
        + encoded_address
        + struct.pack("!H", destination_port)
    )
    response_header = _recv_exact(client, 4)
    assert response_header[0] == 5
    assert response_header[2] == 0
    assert response_header[3] == 1
    _recv_exact(client, 6)
    return client, response_header[1]


@pytest.mark.unit
def test_ipv4_connect_relays_both_directions_and_binds_source_ip() -> None:
    with _echo_server() as destination:
        with source_bound_socks_proxy(source_ip="127.0.0.1") as endpoint:
            assert endpoint.host == "127.0.0.1"
            assert endpoint.port > 0
            assert endpoint.address == (endpoint.host, endpoint.port)

            client, reply_code = _open_socks_connection(
                endpoint.address,
                destination[0],
                destination[1],
                address_type=1,
            )
            with client:
                assert reply_code == 0
                client.sendall(b"through-proxy")
                assert _recv_exact(client, len(b"127.0.0.1|through-proxy")) == b"127.0.0.1|through-proxy"

        with pytest.raises(OSError):
            socket.create_connection(endpoint.address, timeout=0.25)


@pytest.mark.unit
def test_domain_connect_resolves_only_to_ipv4_and_relays_payload() -> None:
    with _echo_server() as destination:
        with source_bound_socks_proxy(source_ip="127.0.0.1") as endpoint:
            client, reply_code = _open_socks_connection(
                endpoint.address,
                "localhost",
                destination[1],
                address_type=3,
            )
            with client:
                assert reply_code == 0
                client.sendall(b"domain-target")
                assert _recv_exact(client, len(b"127.0.0.1|domain-target")) == b"127.0.0.1|domain-target"


@pytest.mark.unit
def test_rejects_unsupported_authentication_method() -> None:
    with source_bound_socks_proxy(source_ip="127.0.0.1") as endpoint:
        with socket.create_connection(endpoint.address, timeout=2) as client:
            client.settimeout(2)
            client.sendall(b"\x05\x01\x02")
            assert _recv_exact(client, 2) == b"\x05\xff"
            assert client.recv(1) == b""


@pytest.mark.unit
def test_rejects_unsupported_command() -> None:
    with source_bound_socks_proxy(source_ip="127.0.0.1") as endpoint:
        client, reply_code = _open_socks_connection(
            endpoint.address,
            "127.0.0.1",
            1,
            address_type=1,
            command=2,
        )
        with client:
            assert reply_code == 7


@pytest.mark.unit
def test_exception_inside_context_still_closes_listener_and_idle_client() -> None:
    endpoint_address: tuple[str, int]
    with pytest.raises(RuntimeError, match="caller failed"):
        with source_bound_socks_proxy(source_ip="127.0.0.1") as endpoint:
            endpoint_address = endpoint.address
            idle_client = socket.create_connection(endpoint.address, timeout=2)
            idle_client.sendall(b"\x05")
            raise RuntimeError("caller failed")

    with idle_client:
        assert idle_client.recv(1) == b""
    with pytest.raises(OSError):
        socket.create_connection(endpoint_address, timeout=0.25)


@pytest.mark.unit
def test_rejects_ipv6_source_address() -> None:
    with pytest.raises(ValueError, match="IPv4"):
        with source_bound_socks_proxy(source_ip="::1"):
            pass
