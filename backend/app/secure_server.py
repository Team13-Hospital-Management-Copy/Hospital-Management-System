import os

from hypercorn.asyncio import serve
from hypercorn.config import Config

from app.main import app


async def main():
    certfile = os.environ.get("TLS_CERTFILE")
    keyfile = os.environ.get("TLS_KEYFILE")

    if not certfile or not keyfile:
        raise RuntimeError(
            "Set TLS_CERTFILE and TLS_KEYFILE to your TLS certificate and key."
        )

    config = Config()
    config.bind = ["0.0.0.0:8443"]
    config.certfile = certfile
    config.keyfile = keyfile

    await serve(app, config)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
