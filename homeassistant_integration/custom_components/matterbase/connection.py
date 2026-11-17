"""Validate the configured local server without requesting inventory credentials."""
import asyncio
from urllib.parse import urlsplit


def server_url(value):
    if not isinstance(value, str):
        raise ValueError("Enter an HTTP(S) Matterbase URL")
    value = value.strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            any(c.isspace() for c in value) or "\\" in value):
        raise ValueError("Use an HTTP(S) URL without credentials, query, or fragment")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid port")
    return value


class EmbeddingDisabled(ValueError):
    """The server still rejects embedding."""


async def validate_server(session, url):
    async with asyncio.timeout(8):
        async with session.get(url + "/api/health", allow_redirects=False) as response:
            if response.status != 200:
                raise ValueError("Matterbase server is not healthy")
            if "frame-ancestors 'none'" in response.headers.get("Content-Security-Policy", ""):
                raise EmbeddingDisabled("Configure MATTERBASE_FRAME_ANCESTORS on the server")
            if (await response.json()).get("status") != "ok":
                raise ValueError("This address is not a healthy Matterbase server")
