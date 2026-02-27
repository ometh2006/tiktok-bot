"""
keep_alive.py — Tiny HTTP server to prevent free-tier hosts from sleeping.

Free platforms like Render, Railway, and Replit spin down containers
after ~15 minutes of inactivity. This starts a minimal HTTP server so
external pinging services (e.g. UptimeRobot, BetterUptime) can keep
the process alive.

Usage:
  Import and call keep_alive() BEFORE starting the bot.
  Or run directly: python keep_alive.py

Ping this URL every 14 minutes with UptimeRobot (free plan).
"""

import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):                          # noqa: N802
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):      # silence default access log
        pass


def keep_alive(port: int | None = None) -> None:
    """Start the health-check HTTP server in a background daemon thread."""
    port = port or int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[keep_alive] Health server running on port {port}")


if __name__ == "__main__":
    keep_alive()
    # Block forever (used when testing standalone)
    threading.Event().wait()
