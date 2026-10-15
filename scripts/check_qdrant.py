"""Check whether the local Qdrant REST API is reachable."""

import os
import sys
from http.client import HTTPConnection, HTTPException
from urllib.parse import urlsplit


def check_qdrant(url: str) -> bool:
    """Return whether Qdrant responds successfully to its health endpoint."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme != "http" or parsed_url.hostname is None:
        print("QDRANT_URL must be an HTTP URL, such as http://localhost:6333.")
        return False

    connection = HTTPConnection(
        parsed_url.hostname,
        parsed_url.port or 80,
        timeout=5,
    )
    try:
        health_path = f"{parsed_url.path.rstrip('/')}/healthz"
        connection.request("GET", health_path)
        response = connection.getresponse()
        if response.status == 200:
            print(f"Qdrant is reachable at {url}.")
            return True
        print(f"Qdrant health check returned HTTP {response.status}.")
    except (HTTPException, OSError, TimeoutError) as error:
        print(
            f"Could not reach Qdrant at {url}: {error}\n"
            "Start it with `docker compose up -d` and try again."
        )
    finally:
        connection.close()
    return False


if __name__ == "__main__":
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    sys.exit(0 if check_qdrant(qdrant_url) else 1)
