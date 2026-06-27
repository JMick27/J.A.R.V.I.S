"""Private local-network phone bridge for JARVIS.

The bridge lets an iPhone Shortcut fetch approved phone-side actions from the
desktop assistant. It does not send texts, emails, or play music by itself; it
only hands the next approved action to a Shortcut that the user controls.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
import threading
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from health_bridge import is_private_client, local_ipv4_address


MAX_REQUEST_BYTES = 16_384


def load_or_create_phone_token(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 24:
            return token
    except OSError:
        pass
    token = secrets.token_urlsafe(24)
    path.write_text(token, encoding="utf-8")
    return token


class PhoneActionQueue:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def enqueue(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = {
            "id": uuid.uuid4().hex,
            "action": action,
            "payload": payload,
            "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        with self._lock:
            actions = self._read_unlocked()
            actions.append(item)
            self._write_unlocked(actions[-25:])
        return item

    def pop_next(self) -> dict[str, Any] | None:
        with self._lock:
            actions = self._read_unlocked()
            if not actions:
                return None
            item = actions.pop(0)
            self._write_unlocked(actions)
            return item

    def pending_count(self) -> int:
        with self._lock:
            return len(self._read_unlocked())

    def clear(self) -> None:
        with self._lock:
            self._write_unlocked([])

    def _read_unlocked(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            actions = payload.get("actions", [])
            return [item for item in actions if isinstance(item, dict)] if isinstance(actions, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _write_unlocked(self, actions: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"actions": actions}, indent=2), encoding="utf-8")
        temporary.replace(self.path)


@dataclass
class PhoneBridgeStatus:
    running: bool
    message: str
    url: str


class PhoneBridgeServer:
    def __init__(self, queue: PhoneActionQueue, token: str, port: int) -> None:
        self.queue = queue
        self.token = token
        self.port = max(1024, min(65535, int(port)))
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.last_error = ""

    @property
    def url(self) -> str:
        return f"http://{local_ipv4_address()}:{self.port}/phone/next"

    def start(self) -> PhoneBridgeStatus:
        if self._server is not None:
            return self.status()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0].rstrip("/") != "/phone/next":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                if not is_private_client(self.client_address[0]):
                    self._reply(403, {"ok": False, "error": "Local-network clients only"})
                    return
                token = self.headers.get("X-JARVIS-Phone-Token", "")
                if not token:
                    token = parse_qs(urlparse(self.path).query).get("token", [""])[0]
                if not secrets.compare_digest(str(token), bridge.token):
                    self._reply(401, {"ok": False, "error": "Pairing code rejected"})
                    return
                item = bridge.queue.pop_next()
                if item is None:
                    self._reply(200, {"ok": True, "action": "none"})
                    return
                payload = item.get("payload", {}) if isinstance(item.get("payload"), dict) else {}
                self._reply(200, {"ok": True, "id": item.get("id"), "action": item.get("action"), **payload})

            def do_POST(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0].rstrip("/") != "/phone/result":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                if not is_private_client(self.client_address[0]):
                    self._reply(403, {"ok": False, "error": "Local-network clients only"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length < 0 or length > MAX_REQUEST_BYTES:
                    self._reply(413, {"ok": False, "error": "Invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._reply(400, {"ok": False, "error": "Invalid JSON"})
                    return
                supplied = str(self.headers.get("X-JARVIS-Phone-Token") or payload.get("token", ""))
                if not secrets.compare_digest(supplied, bridge.token):
                    self._reply(401, {"ok": False, "error": "Pairing code rejected"})
                    return
                self._reply(200, {"ok": True})

            def _reply(self, status: int, payload: dict[str, Any]) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
            self._server.daemon_threads = True
            self._thread = threading.Thread(target=self._server.serve_forever, name="jarvis-phone-bridge", daemon=True)
            self._thread.start()
            self.last_error = ""
        except OSError as exc:
            self._server = None
            self.last_error = str(exc)
        return self.status()

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        self._thread = None

    def status(self) -> PhoneBridgeStatus:
        if self._server is not None:
            return PhoneBridgeStatus(True, "Listening for iPhone Shortcut requests", self.url)
        if self.last_error:
            return PhoneBridgeStatus(False, f"Could not start: {self.last_error}", self.url)
        return PhoneBridgeStatus(False, "Off", self.url)
