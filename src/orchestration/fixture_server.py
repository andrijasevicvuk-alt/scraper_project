"""Internal-only HTTP server that exposes deterministic synthetic fixture data."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import signal
from threading import Event, Thread
from typing import Iterator


SYNTHETIC_LISTING = {
    "source_name": "synthetic_fixture",
    "source_listing_key": "synthetic-listing-001",
    "listing_url": "https://fixture.invalid/listings/synthetic-listing-001",
    "visible_title": "Synthetic fixture boat",
    "visible_price_text": "100000",
    "visible_currency": "EUR",
    "visible_specs": {"length_m": "10.0"},
    "visible_status": "active",
    "card_fingerprint": "synthetic-card-v1",
}


class _FixtureRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required stdlib handler name
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path == "/listing.json":
            self._respond(200, SYNTHETIC_LISTING)
        else:
            self._respond(404, {"error": "not found"})

    def _respond(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        """Keep fixture requests out of process logs."""


@contextmanager
def serve_synthetic_fixture(host: str = "127.0.0.1", port: int = 0) -> Iterator[str]:
    """Start an ephemeral local fixture server for integration tests only."""
    server = ThreadingHTTPServer((host, port), _FixtureRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{host}:{server.server_port}/listing.json"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), _FixtureRequestHandler)
    stop_requested = Event()

    def _request_stop(_signum: int, _frame: object) -> None:
        stop_requested.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    server.timeout = 0.5
    try:
        while not stop_requested.is_set():
            server.handle_request()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
