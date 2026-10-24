from ssl import TLSVersion
from unittest.mock import patch

from hypercorn.config import Config


def test_hypercorn_tls_context_requires_tls_12_or_newer():
    config = Config()
    config.certfile = "server.crt"
    config.keyfile = "server.key"

    with patch("hypercorn.config.create_default_context") as mock_create_context:
        context = mock_create_context.return_value
        config.create_ssl_context()

    assert context.minimum_version == TLSVersion.TLSv1_2
    context.load_cert_chain.assert_called_once_with(
        certfile="server.crt",
        keyfile="server.key",
        password=None,
    )
