"""Private WSGI server; only Nginx exposes a public port in Compose."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.wsgi import application
from waitress import serve

serve(
    application,
    host=os.getenv("WEB_BIND_HOST", "0.0.0.0"),
    port=8000,
    threads=int(os.getenv("WEB_THREADS", "8")),
    connection_limit=int(os.getenv("WEB_CONNECTION_LIMIT", "200")),
    channel_timeout=60,
    max_request_body_size=10 * 1024 * 1024,
    trusted_proxy="*",
    trusted_proxy_headers={"x-forwarded-proto", "x-forwarded-for"},
    trusted_proxy_count=1,
    clear_untrusted_proxy_headers=True,
)
