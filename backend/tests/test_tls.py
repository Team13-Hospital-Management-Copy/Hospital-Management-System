"""US-02 / HMS-SR-001 / TC-Sec-01, TC-Sec-02: TLS 1.2+ for client-server and database connections."""

import asyncio
import os
import socket
import ssl
import threading
import time
from pathlib import Path

import httpx
import pytest

from app.serve import build_server
from app.tls import (
    HTTPS_REQUIRED_MESSAGE,
    InsecureDatabaseConnectionError,
    check_database_tls,
    database_url_requires_tls,
)

FIXTURES = Path(__file__).parent / "fixtures"
CERT = str(FIXTURES / "test-only-cert.pem")
KEY = str(FIXTURES / "test-only-key.pem")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def tls_server():
    """The real app served by `app.serve` (uvicorn + TLS 1.2 minimum) on a random local port."""
    previous = os.environ.get("ENFORCE_HTTPS")
    port = _free_port()
    server = build_server(CERT, KEY, port=port)
    thread = threading.Thread(target=lambda: asyncio.run(server.serve()), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield port
    server.should_exit = True
    thread.join(timeout=5)
    if previous is None:
        os.environ.pop("ENFORCE_HTTPS", None)
    else:
        os.environ["ENFORCE_HTTPS"] = previous


@pytest.fixture(scope="module")
def legacy_tls_server():
    """A deliberately permissive TLS echo server (accepts TLS 1.0+), used only as a control."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.set_ciphers("ALL:@SECLEVEL=0")
    ctx.minimum_version = ssl.TLSVersion.TLSv1
    ctx.load_cert_chain(CERT, KEY)
    listener = socket.create_server(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    stop = threading.Event()

    def serve():
        listener.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = listener.accept()
            except OSError:
                continue
            try:
                with ctx.wrap_socket(conn, server_side=True):
                    pass
            except (ssl.SSLError, OSError):
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port
    stop.set()
    thread.join(timeout=2)
    listener.close()


def _handshake(port: int, version: ssl.TLSVersion) -> str:
    """Try a TLS handshake pinned to exactly `version`; return the negotiated version."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("ALL:@SECLEVEL=0")  # let the *client* offer legacy TLS so the server is what refuses it
    ctx.minimum_version = version
    ctx.maximum_version = version
    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
        with ctx.wrap_socket(raw, server_hostname="localhost") as tls:
            return tls.version()


@pytest.mark.parametrize("version", [ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1])
def test_tc_sec_01_handshakes_below_tls_1_2_are_rejected(tls_server, legacy_tls_server, version):
    # Control: the same client *can* negotiate this legacy version with a permissive server, so the
    # failure below really is our server refusing it (not the client being unable to try).
    try:
        _handshake(legacy_tls_server, version)
    except (ssl.SSLError, ConnectionResetError):
        pytest.skip(f"this machine's OpenSSL cannot offer {version.name} at all; covered by the minimum_version test")
    with pytest.raises((ssl.SSLError, ConnectionResetError)):
        _handshake(tls_server, version)


@pytest.mark.parametrize("version,expected", [(ssl.TLSVersion.TLSv1_2, "TLSv1.2"), (ssl.TLSVersion.TLSv1_3, "TLSv1.3")])
def test_tc_sec_01_tls_1_2_and_1_3_are_accepted(tls_server, version, expected):
    assert _handshake(tls_server, version) == expected


def test_tc_sec_01_server_context_minimum_version_is_tls_1_2():
    config = build_server(CERT, KEY, port=_free_port()).config
    config.load()

    assert config.ssl.minimum_version == ssl.TLSVersion.TLSv1_2


def test_tc_sec_01_plaintext_http_is_rejected_on_the_tls_port(tls_server):
    with pytest.raises(httpx.HTTPError):
        httpx.get(f"http://127.0.0.1:{tls_server}/doctors", timeout=5)


def test_tc_sec_01_https_request_works_and_sets_hsts(tls_server):
    response = httpx.get(f"https://127.0.0.1:{tls_server}/doctors", verify=False, timeout=5)

    assert response.status_code == 401  # reached the app over TLS; the endpoint needs login
    assert response.headers["strict-transport-security"].startswith("max-age=")


def test_https_only_middleware_rejects_plain_http_behind_a_proxy(client, monkeypatch):
    monkeypatch.setenv("ENFORCE_HTTPS", "1")
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")

    plain = client.get("/doctors", headers={"X-Forwarded-Proto": "http"})
    secure = client.get("/doctors", headers={"X-Forwarded-Proto": "https"})

    assert plain.status_code == 403
    assert plain.json()["detail"] == HTTPS_REQUIRED_MESSAGE
    assert secure.status_code == 401  # passed the HTTPS check, then normal auth applies
    assert "strict-transport-security" in secure.headers


@pytest.mark.parametrize(
    "url,secure",
    [
        ("sqlite:///./hms.db", True),
        ("postgresql://u:p@db.example/hms?sslmode=verify-full", True),
        ("postgresql+psycopg://u:p@db.example/hms?sslmode=require", True),
        ("postgresql://u:p@db.example/hms", False),
        ("postgresql://u:p@db.example/hms?sslmode=prefer", False),
        ("mysql+pymysql://u:p@db.example/hms?ssl_mode=VERIFY_IDENTITY", True),
        ("mysql+pymysql://u:p@db.example/hms", False),
    ],
)
def test_tc_sec_02_database_url_must_force_tls(url, secure):
    assert database_url_requires_tls(url) is secure


def test_tc_sec_02_app_refuses_an_unencrypted_database(monkeypatch):
    monkeypatch.delenv("REQUIRE_DB_TLS", raising=False)
    with pytest.raises(InsecureDatabaseConnectionError):
        check_database_tls("postgresql://u:p@db.example/hms")

    monkeypatch.setenv("REQUIRE_DB_TLS", "0")
    check_database_tls("postgresql://u:p@db.example/hms")  # explicit opt-out for a local test DB
