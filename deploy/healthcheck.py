"""Readiness check includes PostgreSQL; the endpoint discloses no credentials."""
import os
from urllib.request import Request, urlopen

request = Request("http://127.0.0.1:8000/health/", headers={
    "Host": os.getenv("HEALTHCHECK_HOST", "localhost"),
    "X-Forwarded-Proto": "https",
})
with urlopen(request, timeout=8) as response:
    if response.status != 200:
        raise SystemExit(1)
