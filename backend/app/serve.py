"""Run the API over HTTPS with TLS 1.2 as the minimum version (US-02).

    python -m app.serve --certfile cert.pem --keyfile key.pem [--host 0.0.0.0] [--port 8443]

Plaintext HTTP is not served at all on this port, and handshakes below TLS 1.2 are refused.
"""

import argparse
import os

import uvicorn

from .tls import enforce_minimum_tls


class Tls12Config(uvicorn.Config):
    def load(self) -> None:
        super().load()
        if self.ssl is None:
            raise SystemExit("A certificate and key are required: refusing to serve over plaintext HTTP.")
        enforce_minimum_tls(self.ssl)


def build_server(certfile: str, keyfile: str, host: str = "127.0.0.1", port: int = 8443) -> uvicorn.Server:
    os.environ.setdefault("ENFORCE_HTTPS", "1")
    config = Tls12Config(
        "app.main:app",
        host=host,
        port=port,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        log_level="info",
    )
    return uvicorn.Server(config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    args = parser.parse_args()
    build_server(args.certfile, args.keyfile, args.host, args.port).run()


if __name__ == "__main__":
    main()
