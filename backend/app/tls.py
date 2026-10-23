"""US-02 / HMS-SR-001, HMS-NF-003: TLS 1.2+ for client-server and server-database connections."""

import os
import ssl
from urllib.parse import parse_qs, urlsplit

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# AC-HMS-SR-001: connections using TLS below 1.2 (or plaintext) are rejected.
MIN_TLS_VERSION = ssl.TLSVersion.TLSv1_2

HTTPS_REQUIRED_MESSAGE = "HTTPS (TLS 1.2 or higher) is required."
HSTS_HEADER_VALUE = "max-age=31536000; includeSubDomains"


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


# --- Client <-> server ---------------------------------------------------------------------


def create_server_ssl_context(certfile: str, keyfile: str | None = None) -> ssl.SSLContext:
    """Server-side TLS context that refuses anything older than TLS 1.2."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = MIN_TLS_VERSION
    context.load_cert_chain(certfile, keyfile)
    return context


def enforce_minimum_tls(context: ssl.SSLContext) -> ssl.SSLContext:
    if context.minimum_version < MIN_TLS_VERSION:
        context.minimum_version = MIN_TLS_VERSION
    return context


class HttpsOnlyMiddleware(BaseHTTPMiddleware):
    """Rejects plaintext HTTP requests and tells browsers to stay on HTTPS (HSTS).

    Enabled with ENFORCE_HTTPS=1 (on by default when served via `python -m app.serve`). When a
    TLS-terminating proxy sits in front of the app, set TRUST_PROXY_HEADERS=1 so the proxy's
    X-Forwarded-Proto header is used to decide whether the original request was HTTPS.
    """

    async def dispatch(self, request: Request, call_next):
        if not _env_flag("ENFORCE_HTTPS", False):
            return await call_next(request)

        scheme = request.url.scheme
        if _env_flag("TRUST_PROXY_HEADERS", False):
            scheme = request.headers.get("x-forwarded-proto", scheme).split(",")[0].strip().lower()

        if scheme != "https":
            return JSONResponse({"detail": HTTPS_REQUIRED_MESSAGE}, status_code=403)

        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = HSTS_HEADER_VALUE
        return response


# --- Server <-> database -------------------------------------------------------------------

# Driver URL options that mean "the connection must be encrypted".
_POSTGRES_SECURE_SSLMODES = {"require", "verify-ca", "verify-full"}
_MYSQL_SECURE_SSL_MODES = {"required", "verify_ca", "verify_identity"}


class InsecureDatabaseConnectionError(RuntimeError):
    pass


def database_url_requires_tls(url: str) -> bool:
    """True if the URL forces an encrypted connection, or is a local SQLite file (no network)."""
    parts = urlsplit(url)
    scheme = parts.scheme.split("+")[0].lower()
    params = {k.lower(): v[-1].lower() for k, v in parse_qs(parts.query).items()}

    if scheme == "sqlite":
        return True
    if scheme in {"postgresql", "postgres"}:
        return params.get("sslmode") in _POSTGRES_SECURE_SSLMODES
    if scheme in {"mysql", "mariadb"}:
        return params.get("ssl_mode") in _MYSQL_SECURE_SSL_MODES or "ssl_ca" in params
    return False


def check_database_tls(url: str) -> None:
    """Refuse to start against a networked database unless the connection is forced onto TLS.

    Set REQUIRE_DB_TLS=0 only for a throwaway local database.
    """
    if not _env_flag("REQUIRE_DB_TLS", True):
        return
    if not database_url_requires_tls(url):
        raise InsecureDatabaseConnectionError(
            "DATABASE_URL must force an encrypted connection (e.g. ?sslmode=verify-full for PostgreSQL "
            "or ?ssl_mode=VERIFY_IDENTITY for MySQL). Set REQUIRE_DB_TLS=0 only for a local test database."
        )
