"""Small local SOCKS5 proxy whose IPv4 connections use a fixed source address."""

from __future__ import annotations

import errno
import ipaddress
import select
import socket
import socketserver
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

_SOCKS_VERSION = 5
_NO_AUTH = 0
_NO_ACCEPTABLE_AUTH = 0xFF
_CONNECT = 1
_IPV4 = 1
_DOMAIN = 3

_SUCCEEDED = 0
_GENERAL_FAILURE = 1
_NOT_ALLOWED = 2
_NETWORK_UNREACHABLE = 3
_HOST_UNREACHABLE = 4
_CONNECTION_REFUSED = 5
_COMMAND_NOT_SUPPORTED = 7
_ADDRESS_TYPE_NOT_SUPPORTED = 8


class _SourceBoundServer(socketserver.ThreadingTCPServer):
    address_family = socket.AF_INET
    allow_reuse_address = True
    daemon_threads = False
    block_on_close = True

    def __init__(
        self,
        server_address: tuple[str, int],
        source_ip: str,
        connect_timeout: float,
    ) -> None:
        self.source_ip = source_ip
        self.connect_timeout = connect_timeout
        self.shutdown_requested = threading.Event()
        super().__init__(server_address, _SocksRequestHandler)
        self.timeout = 0.1

    def serve_until_shutdown(self) -> None:
        while not self.shutdown_requested.is_set():
            self.handle_request()

    def handle_error(
        self,
        request: socket.socket,
        client_address: tuple[str, int],
    ) -> None:
        # A malformed or interrupted client must not make socketserver print
        # connection contents or incidental endpoint information to stderr.
        return


class _SocksRequestHandler(socketserver.BaseRequestHandler):
    server: _SourceBoundServer
    request: socket.socket

    def handle(self) -> None:
        self.request.settimeout(0.25)
        try:
            if not self._accept_no_auth():
                return
            self._connect_and_relay()
        except (ConnectionError, OSError, UnicodeError, ValueError):
            return

    def _accept_no_auth(self) -> bool:
        version, method_count = self._recv_exact(2)
        methods = self._recv_exact(method_count)
        if version != _SOCKS_VERSION or _NO_AUTH not in methods:
            if version == _SOCKS_VERSION:
                self.request.sendall(bytes((_SOCKS_VERSION, _NO_ACCEPTABLE_AUTH)))
            return False
        self.request.sendall(bytes((_SOCKS_VERSION, _NO_AUTH)))
        return True

    def _connect_and_relay(self) -> None:
        version, command, reserved, address_type = self._recv_exact(4)
        if version != _SOCKS_VERSION or reserved != 0:
            self._send_reply(_GENERAL_FAILURE)
            return
        if command != _CONNECT:
            self._send_reply(_COMMAND_NOT_SUPPORTED)
            return

        if address_type == _IPV4:
            host = socket.inet_ntoa(self._recv_exact(4))
        elif address_type == _DOMAIN:
            host_length = self._recv_exact(1)[0]
            if host_length == 0:
                self._send_reply(_HOST_UNREACHABLE)
                return
            host = self._recv_exact(host_length).decode("idna")
        else:
            self._send_reply(_ADDRESS_TYPE_NOT_SUPPORTED)
            return
        port = struct.unpack("!H", self._recv_exact(2))[0]

        try:
            outbound = self._open_outbound(host, port)
        except OSError as exc:
            self._send_reply(_reply_for_error(exc))
            return

        with outbound:
            bound_host, bound_port = outbound.getsockname()[:2]
            self._send_reply(_SUCCEEDED, str(bound_host), int(bound_port))
            self._relay(outbound)

    def _open_outbound(self, host: str, port: int) -> socket.socket:
        try:
            addresses = socket.getaddrinfo(
                host,
                port,
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except socket.gaierror as exc:
            raise OSError(errno.EHOSTUNREACH, str(exc)) from exc

        last_error: OSError | None = None
        for family, socktype, protocol, _, address in addresses:
            outbound = socket.socket(family, socktype, protocol)
            try:
                outbound.settimeout(self.server.connect_timeout)
                outbound.bind((self.server.source_ip, 0))
                outbound.connect(address)
                outbound.settimeout(0.25)
                return outbound
            except OSError as exc:
                last_error = exc
                outbound.close()

        if last_error is not None:
            raise last_error
        raise OSError(errno.EHOSTUNREACH, "destination has no IPv4 address")

    def _relay(self, outbound: socket.socket) -> None:
        peers = {self.request: outbound, outbound: self.request}
        readable: list[socket.socket] = [self.request, outbound]

        while readable and not self.server.shutdown_requested.is_set():
            ready, _, _ = select.select(readable, [], [], 0.25)
            for source in ready:
                destination = peers[source]
                data = source.recv(65536)
                if not data:
                    readable.remove(source)
                    try:
                        destination.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                    continue
                destination.sendall(data)

    def _recv_exact(self, size: int) -> bytes:
        received = bytearray()
        while len(received) < size:
            if self.server.shutdown_requested.is_set():
                raise ConnectionAbortedError("proxy is shutting down")
            try:
                chunk = self.request.recv(size - len(received))
            except TimeoutError:
                continue
            if not chunk:
                raise ConnectionError("client disconnected")
            received.extend(chunk)
        return bytes(received)

    def _send_reply(self, reply_code: int, bound_host: str = "0.0.0.0", bound_port: int = 0) -> None:
        response = (
            bytes((_SOCKS_VERSION, reply_code, 0, _IPV4))
            + socket.inet_aton(bound_host)
            + struct.pack("!H", bound_port)
        )
        self.request.sendall(response)


def _reply_for_error(exc: OSError) -> int:
    return {
        errno.EACCES: _NOT_ALLOWED,
        errno.EPERM: _NOT_ALLOWED,
        errno.ENETUNREACH: _NETWORK_UNREACHABLE,
        errno.EHOSTUNREACH: _HOST_UNREACHABLE,
        errno.ECONNREFUSED: _CONNECTION_REFUSED,
    }.get(exc.errno, _GENERAL_FAILURE)


@dataclass(frozen=True, slots=True)
class SocksProxyEndpoint:
    """Address of a running local SOCKS proxy."""

    host: str
    port: int

    @property
    def address(self) -> tuple[str, int]:
        return self.host, self.port


class _SourceBoundSocksProxy:
    """Threaded loopback SOCKS5 CONNECT proxy with source-bound IPv4 egress."""

    def __init__(
        self,
        source_ip: str,
        *,
        listen_port: int = 0,
        connect_timeout: float = 10.0,
    ) -> None:
        parsed_source_ip = ipaddress.ip_address(source_ip)
        if not isinstance(parsed_source_ip, ipaddress.IPv4Address):
            raise ValueError("source_ip must be an IPv4 address")
        if not 0 <= listen_port <= 65535:
            raise ValueError("listen_port must be between 0 and 65535")
        if connect_timeout <= 0:
            raise ValueError("connect_timeout must be positive")

        self.source_ip = str(parsed_source_ip)
        self.listen_port = listen_port
        self.connect_timeout = connect_timeout
        self._server: _SourceBoundServer | None = None
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.Lock()

    @property
    def address(self) -> tuple[str, int]:
        server = self._server
        if server is None:
            raise RuntimeError("proxy is not running")
        host, port = server.server_address[:2]
        return str(host), int(port)

    @property
    def host(self) -> str:
        return self.address[0]

    @property
    def port(self) -> int:
        return self.address[1]

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> tuple[str, int]:
        """Start the proxy and return its bound ``(host, port)`` address."""
        with self._lifecycle_lock:
            if self.is_running:
                return self.address

            server = _SourceBoundServer(
                ("127.0.0.1", self.listen_port),
                self.source_ip,
                self.connect_timeout,
            )
            thread = threading.Thread(
                target=server.serve_until_shutdown,
                name="source-bound-socks-proxy",
                daemon=True,
            )
            self._server = server
            self._thread = thread
            try:
                thread.start()
            except BaseException:
                server.server_close()
                self._server = None
                self._thread = None
                raise
            return self.address

    def close(self) -> None:
        """Stop accepting connections and close all active relay threads."""
        with self._lifecycle_lock:
            server = self._server
            thread = self._thread
            if server is None:
                return

            server.shutdown_requested.set()
            if thread is not None:
                thread.join()
            server.server_close()
            self._server = None
            self._thread = None


@contextmanager
def source_bound_socks_proxy(
    source_ip: str,
    *,
    listen_port: int = 0,
    connect_timeout: float = 10.0,
) -> Iterator[SocksProxyEndpoint]:
    """Run a loopback-only SOCKS5 proxy and yield its local endpoint."""
    proxy = _SourceBoundSocksProxy(
        source_ip,
        listen_port=listen_port,
        connect_timeout=connect_timeout,
    )
    host, port = proxy.start()
    try:
        yield SocksProxyEndpoint(host=host, port=port)
    finally:
        proxy.close()
