"""Private ASGI server; Nginx handles the public HTTP/WebSocket endpoint."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn

uvicorn.run(
    "config.asgi:application",
    host=os.getenv("WEB_BIND_HOST", "0.0.0.0"),
    port=8000,
    proxy_headers=True,
    forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "*"),
    ws_max_size=16384,
    ws_ping_interval=20,
    ws_ping_timeout=20,
)
