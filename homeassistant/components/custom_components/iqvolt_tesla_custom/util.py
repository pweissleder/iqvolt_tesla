"""Utilities for tesla."""
from homeassistant.util.ssl import create_no_verify_ssl_context

try:
    # Home Assistant 2023.4.x+
    from homeassistant.util.ssl import get_default_context

    SSL_CONTEXT = create_no_verify_ssl_context()
except ImportError:
    from homeassistant.util.ssl import client_context

    SSL_CONTEXT = client_context()
