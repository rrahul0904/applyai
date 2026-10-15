"""Exercise HTTPX/httpcore's actual transport and concrete sockets without external traffic."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import ssl
from threading import Thread

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import pytest

from app.jobs.web_security import PublicUrlRejected, SafeHttpFetcher, _PublicDnsPinnedBackend

PUBLIC_IP = "93.184.216.34"
OTHER_PUBLIC_IP = "1.1.1.1"


def public_resolver(host, port):
    address = OTHER_PUBLIC_IP if host == "redirect.example" else PUBLIC_IP
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]


@contextmanager
def transport_server(tmp_path, monkeypatch, *, secure=False, redirect=None):
    requests, connections, server_names = [], [], []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.headers["Host"], self.path))
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", redirect.format(port=self.server.server_port))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            payload = b"real concrete backend response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    if secure:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "jobs.example")])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName("jobs.example")]), critical=False)
                .sign(key, hashes.SHA256()))
        cert_path, key_path = tmp_path / "certificate.pem", tmp_path / "key.pem"
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(cert_path, key_path)
        server_context.set_servername_callback(lambda sock, hostname, context: server_names.append(hostname))
        server.socket = server_context.wrap_socket(server.socket, server_side=True)
        trusted_context = ssl.create_default_context(cafile=str(cert_path))
        # Change test trust only; retain the default Client, transport, pool and concrete backend.
        monkeypatch.setattr("httpx._transports.default.create_ssl_context", lambda **kwargs: trusted_context)

    original_connect = socket.create_connection

    def connect_to_fixture(address, timeout=None, source_address=None, **kwargs):
        # The production concrete backend must receive a validated literal, never the DNS name.
        assert address[0] in {PUBLIC_IP, OTHER_PUBLIC_IP}
        assert address[1] == server.server_port
        connections.append(address)
        return original_connect(("127.0.0.1", server.server_port), timeout,
                                source_address=source_address, **kwargs)

    monkeypatch.setattr(socket, "create_connection", connect_to_fixture)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, requests, connections, server_names
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("secure", [False, True])
def test_default_transport_uses_concrete_socket_and_preserves_host_and_tls_name(tmp_path, monkeypatch, secure):
    with transport_server(tmp_path, monkeypatch, secure=secure) as (port, requests, connections, names):
        fetcher = SafeHttpFetcher(resolver=public_resolver)
        try:
            assert fetcher._owns_client
            assert isinstance(fetcher.client._transport._pool._network_backend, _PublicDnsPinnedBackend)
            result = fetcher.fetch(f"{'https' if secure else 'http'}://jobs.example:{port}/role")
            assert result.status_code == 200
            assert result.content == b"real concrete backend response"
            assert result.final_url.endswith(f"jobs.example:{port}/role")
            assert requests == [(f"jobs.example:{port}", "/role")]
            assert connections == [(PUBLIC_IP, port)]
            assert names == (["jobs.example"] if secure else [])
        finally:
            fetcher.close()


def test_default_transport_validates_and_repins_each_public_redirect_host(tmp_path, monkeypatch):
    # The redirect changes host and its validated IP; the host header still names the destination.
    with transport_server(tmp_path, monkeypatch, redirect="http://redirect.example:{port}/role") as (port, requests, connections, _):
        fetcher = SafeHttpFetcher(resolver=public_resolver)
        try:
            result = fetcher.fetch(f"http://jobs.example:{port}/redirect")
            assert result.status_code == 200
            assert result.final_url == f"http://redirect.example:{port}/role"
            assert requests == [(f"jobs.example:{port}", "/redirect"), (f"redirect.example:{port}", "/role")]
            assert connections == [(PUBLIC_IP, port), (OTHER_PUBLIC_IP, port)]
        finally:
            fetcher.close()


def test_default_transport_blocks_private_redirect_before_connecting(tmp_path, monkeypatch):
    with transport_server(tmp_path, monkeypatch, redirect="http://127.0.0.1/private") as (port, requests, connections, _):
        fetcher = SafeHttpFetcher(resolver=public_resolver)
        try:
            with pytest.raises(PublicUrlRejected, match="non-public address"):
                fetcher.fetch(f"http://jobs.example:{port}/redirect")
            assert len(requests) == 1
            assert connections == [(PUBLIC_IP, port)]
        finally:
            fetcher.close()


def test_default_transport_blocks_mixed_public_private_dns_before_any_socket(monkeypatch):
    def mixed_resolver(host, port):
        return public_resolver(host, port) + [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    def unexpected_socket(*args, **kwargs):
        raise AssertionError("Rejected DNS answer must not create a connection")

    monkeypatch.setattr(socket, "create_connection", unexpected_socket)
    fetcher = SafeHttpFetcher(resolver=mixed_resolver)
    try:
        with pytest.raises(PublicUrlRejected, match="non-public address"):
            fetcher.fetch("http://jobs.example/role")
    finally:
        fetcher.close()
