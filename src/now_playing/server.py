"""Local display HTTP server with an explicit route allowlist."""

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit

from .albums import KEY
from .models import DisplayState

ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/mosaic.js": ("mosaic.js", "text/javascript; charset=utf-8"),
    "/artwork.svg": ("artwork.svg", "image/svg+xml"),
    "/demo-artwork.svg": ("demo-artwork.svg", "image/svg+xml"),
}


def response_for(path: str, state: Callable[[], DisplayState], albums=None, artwork=None):
    path = urlsplit(path).path
    if path == "/api/albums":
        try:
            collection = albums() if albums else {"revision": 0, "albums": []}
            return 200, "application/json", json.dumps(collection).encode()
        except Exception:
            return 503, "application/json", b'{"error":"Album collection unavailable"}'
    if path.startswith("/artwork/") and artwork:
        try:
            image = artwork(path.removeprefix("/artwork/"))
            if image:
                return 200, image[0], image[1]
        except Exception:
            return 503, "text/plain", b"Artwork unavailable"
    if path == "/api/state":
        return 200, "application/json", json.dumps(state().to_dict()).encode()
    if path in ASSETS:
        name, mime = ASSETS[path]
        asset = files("now_playing").joinpath("web", name)
        if asset.is_file():
            return 200, mime, asset.read_bytes()
    return 404, "text/plain; charset=utf-8", b"Not found"


class Server:
    def __init__(
        self,
        state: Callable[[], DisplayState],
        host="127.0.0.1",
        port=8080,
        albums=None,
        artwork=None,
        delete_album=None,
    ):
        class Handler(BaseHTTPRequestHandler):
            def do_DELETE(self):
                origin = self.headers.get("Origin")
                if (
                    origin and origin != "http://" + self.headers.get("Host", "")
                ) or self.headers.get("Sec-Fetch-Site") == "cross-site":
                    self._send(403, "application/json", b'{"error":"Origin rejected"}')
                    return
                path = urlsplit(self.path).path
                if not path.startswith("/api/albums/") or delete_album is None:
                    self._send(404, "application/json", b'{"error":"Not found"}')
                    return
                key = path.removeprefix("/api/albums/")
                if not KEY.fullmatch(key):
                    self._send(400, "application/json", b'{"error":"Invalid album"}')
                    return
                try:
                    delete_album(key)
                    self._send(200, "application/json", b'{"deleted":true}')
                except Exception:
                    self._send(503, "application/json", b'{"error":"Album deletion unavailable"}')

            def do_GET(self):
                self._respond(False)

            def do_HEAD(self):
                self._respond(True)

            def _respond(self, head):
                code, mime, data = response_for(self.path, state, albums, artwork)
                self._send(code, mime, data, head)

            def _send(self, code, mime, data, head=False):
                self.send_response(code)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header(
                    "Cache-Control",
                    "public, max-age=86400"
                    if self.path.startswith("/artwork/") and code == 200
                    else "no-store",
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if not head:
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, ConnectionResetError):
                        pass

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer((host, port), Handler)
        self.http.daemon_threads = True
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
