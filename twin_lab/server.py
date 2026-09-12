"""Single-user loopback HTTP adapter. Not a production web server."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from .schemas import ValidationError, canonical_json, exact_keys, read_json, validate_id
from .governance import DOCUMENTS, DOCUMENT_FILES
from .store import Conflict, NotFound, Store

STATIC = Path(__file__).resolve().parent / "static"
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
          "/snapshot.js": ("snapshot.js", "text/javascript; charset=utf-8"),
          "/review.js": ("review.js", "text/javascript; charset=utf-8"),
          "/api.js": ("api.js", "text/javascript; charset=utf-8"),
          "/lab.js": ("lab.js", "text/javascript; charset=utf-8"),
          "/collection.js": ("collection.js", "text/javascript; charset=utf-8"),
          "/planning-ui.js": ("planning-ui.js", "text/javascript; charset=utf-8"),
          "/governance.js": ("governance.js", "text/javascript; charset=utf-8"),
          "/governance-form.js": ("governance-form.js", "text/javascript; charset=utf-8"),
          "/capture-mode.js": ("capture-mode.js", "text/javascript; charset=utf-8"),
          "/lifecycle.js": ("lifecycle.js", "text/javascript; charset=utf-8"),
          "/planning.css": ("planning.css", "text/css; charset=utf-8"),
          "/styles.css": ("styles.css", "text/css; charset=utf-8")}
MAX_BODY = 131072
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class RequestError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class Handler(BaseHTTPRequestHandler):
    server_version = "TwinLab/0.1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, _format, *args):
        # Intentionally omit access logs: local codes/response text must not leak.
        return

    def reply(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        content = body if isinstance(body, bytes) else canonical_json(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(content)

    def check_local_request(self):
        port = self.server.server_address[1]
        hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
        host = self.headers.get("Host")
        if len(self.headers.get_all("Host", [])) != 1 or host not in hosts:
            raise RequestError(403, "Twin Lab accepts loopback hostnames only.")
        origins = self.headers.get_all("Origin", [])
        if len(origins) > 1 or (origins and origins[0] != f"http://{host}"):
            raise RequestError(403, "Cross-origin access is not allowed.")
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            raise RequestError(403, "Open Twin Lab directly on this machine.")

    def request_body(self):
        if self.headers.get("X-Twin-Lab") != "1":
            raise RequestError(403, "The local Twin Lab request header is required.")
        if self.headers.get_content_type() != "application/json":
            raise RequestError(415, "Use application/json.")
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1:
            raise RequestError(400, "A single Content-Length is required.")
        try:
            length = int(lengths[0])
        except ValueError as exc:
            raise RequestError(400, "Invalid Content-Length.") from exc
        if length < 1:
            raise RequestError(400, "A JSON request body is required.")
        if length > MAX_BODY:
            raise RequestError(413, "Request is too large; shorten the response text.")
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestError(400, "Incomplete request body.")
        return read_json(body)

    def dispatch(self):
        try:
            self.check_local_request()
            path = urlsplit(self.path).path
            store = self.server.store
            if self.command == "GET":
                if path in ASSETS:
                    file, content_type = ASSETS[path]
                    self.reply(200, (STATIC / file).read_bytes(), content_type)
                elif path == "/api/cases":
                    self.reply(200, {"cases": store.cases()})
                elif path == "/api/responses":
                    self.reply(200, {"responses": store.responses()})
                elif path == "/api/catalog":
                    self.reply(200, store.catalog.overview())
                elif path == "/api/collection":
                    self.reply(200, store.collection.overview())
                elif path == "/api/governance":
                    self.reply(200, store.governance.overview())
                elif path.startswith("/api/governance-documents/"):
                    kind = path.removeprefix("/api/governance-documents/")
                    if kind not in DOCUMENT_FILES:
                        raise NotFound("Governance document not found.")
                    filename, content_type = DOCUMENT_FILES[kind]
                    self.reply(200, (DOCUMENTS / filename).read_bytes(), content_type,
                               filename=filename)
                elif path == "/api/lifecycle":
                    self.reply(200, store.lifecycle.overview())
                elif path.startswith("/api/permissions/"):
                    receipt_id = validate_id(path.removeprefix("/api/permissions/"))
                    self.reply(200, store.governance.receipt(receipt_id),
                               filename=f"twin-lab-permission-{receipt_id}.json")
                elif path == "/api/export":
                    exported, manifest = store.lifecycle.managed_export(store.export())
                    self.reply(200, exported, filename=manifest["filename"])
                else:
                    raise NotFound("Page not found.")
            elif self.command == "POST":
                body = self.request_body()
                if path == "/api/presentations":
                    selectors = ("case_id", "version_id", "assignment_id", "supersedes_response_id")
                    selected = set(body).intersection(selectors) if isinstance(body, dict) else set()
                    if len(selected) != 1:
                        raise ValidationError("Choose exactly one presentation selector.")
                    if set(body) == selected:
                        raise ValidationError("Capture now requires an explicit mode. Keep any unsaved answers, then reload Twin Lab and reopen the case.")
                    exact_keys(body, selected | {"capture_mode", "permission_receipt_id", "qa_acknowledged"})
                    self.reply(201, store.present(**body))
                elif path == "/api/responses":
                    exact_keys(body, {"presentation_id", "values"})
                    response, duplicate = store.submit(body["presentation_id"], body["values"])
                    self.reply(200 if duplicate else 201, {"response": response, "duplicate": duplicate})
                else:
                    mutations = {
                        "/api/case-reviews": (store.catalog.add_review, "review"),
                        "/api/case-versions": (store.catalog.add_version, "version"),
                        "/api/protocols": (store.collection.save_protocol, "protocol"),
                        "/api/assignments": (store.collection.assign, "assignment"),
                        "/api/backups": (store.collection.backup, "backup"),
                        "/api/governance": (store.governance.save, "governance"),
                        "/api/permissions": (store.governance.permission, "receipt"),
                        "/api/withdrawals": (store.lifecycle.withdraw, "withdrawal"),
                        "/api/withdrawal-verifications": (store.lifecycle.verify_withdrawal, "verification"),
                        "/api/holds": (store.lifecycle.hold, "hold"),
                        "/api/hold-releases": (store.lifecycle.release_hold, "release"),
                    }
                    if path not in mutations:
                        raise NotFound("Endpoint not found.")
                    mutate, key = mutations[path]
                    record, duplicate = mutate(body)
                    self.reply(200 if duplicate else 201, {key: record, "duplicate": duplicate})
            else:
                raise RequestError(405, "Method not allowed.")
        except RequestError as exc:
            self.reply(exc.status, {"error": exc.message})
        except ValidationError as exc:
            self.reply(400, {"error": str(exc)})
        except Conflict as exc:
            self.reply(409, {"error": str(exc)})
        except NotFound as exc:
            self.reply(404, {"error": str(exc)})
        except (sqlite3.Error, OSError, RuntimeError):
            logging.error("Local storage/request operation failed; no response content logged.")
            self.reply(500, {"error": "Local storage is unavailable. Save was not confirmed. Keep this form open and retry; check the data directory permissions and disk space."})

    do_GET = dispatch
    do_POST = dispatch
    do_OPTIONS = dispatch


def make_server(store, host="127.0.0.1", port=0):
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = store
    return server


def main():
    parser = argparse.ArgumentParser(description="Twin Lab synthetic prototype (local only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--container-bind", action="store_true",
                        help="Listen inside Docker; publish the port on host loopback only.")
    parser.add_argument("--data-dir", type=Path,
                        default=Path.home() / ".local" / "share" / "twin-lab")
    args = parser.parse_args()
    os.umask(0o077)
    store = Store(args.data_dir / "twin-lab.sqlite3")
    server = make_server(store, "0.0.0.0" if args.container_bind else "127.0.0.1", args.port)
    print(f"Twin Lab synthetic prototype: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Twin Lab stopped.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
