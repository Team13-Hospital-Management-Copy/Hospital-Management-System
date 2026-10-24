import ssl


def create_tls_server_context(
    certfile: str,
    keyfile: str,
) -> ssl.SSLContext:
    """Create a server SSL context that requires TLS 1.2 or newer."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context