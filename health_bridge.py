"""Private local-network health bridge for ATLAS.

The bridge accepts small JSON updates from an iPhone Shortcut. It deliberately
does not contact Apple, Gemini, or any cloud service. Health samples remain in a
short rolling file on the PC and are treated as wellness context, not diagnoses.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import json
import re
import secrets
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import median
from typing import Any, Callable


MAX_REQUEST_BYTES = 16_384
MAX_STORED_READINGS = 2_000


def load_or_create_pairing_token(path: Path) -> str:
    """Return a stable local pairing token without placing it in settings.json."""
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


def local_ipv4_address() -> str:
    """Find the LAN address an iPhone should use to reach this PC."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 80))
        address = str(probe.getsockname()[0])
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    finally:
        probe.close()
    try:
        for address in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ipaddress.ip_address(address).is_private and not address.startswith("127."):
                return address
    except OSError:
        pass
    return "127.0.0.1"


def is_private_client(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
        return parsed.is_private or parsed.is_loopback
    except ValueError:
        return False


def _number(payload: dict[str, Any], names: tuple[str, ...], minimum: float, maximum: float) -> float | None:
    for name in names:
        value = payload.get(name)
        if value in (None, ""):
            continue
        try:
            if isinstance(value, str):
                match = re.search(r"-?\d+(?:\.\d+)?", value)
                if not match:
                    raise ValueError
                number = float(match.group(0))
            else:
                number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a number") from exc
        if not minimum <= number <= maximum:
            raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}")
        return round(number, 2)
    return None


def normalize_health_payload(payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate and normalize the limited health fields accepted from Shortcuts."""
    if not isinstance(payload, dict):
        raise ValueError("The request must contain a JSON object")
    heart_rate = _number(payload, ("heart_rate_bpm", "heart_rate", "bpm"), 25, 240)
    hrv = _number(payload, ("hrv_ms", "hrv", "hrv_sdnn"), 1, 500)
    resting_rate = _number(payload, ("resting_heart_rate_bpm", "resting_heart_rate"), 25, 180)
    if heart_rate is None and hrv is None and resting_rate is None:
        raise ValueError("Include heart_rate, hrv, or resting_heart_rate")

    timestamp = str(payload.get("timestamp") or "").strip()
    if timestamp:
        try:
            parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            timestamp = parsed.astimezone().isoformat(timespec="seconds") if parsed.tzinfo else parsed.isoformat(timespec="seconds")
        except ValueError:
            timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    else:
        timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    activity = str(payload.get("activity") or (context or {}).get("stated_activity") or "unspecified").strip()
    source = str(payload.get("source") or "Apple Health Shortcut").strip()
    reading = {
        "timestamp": timestamp,
        "received_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "heart_rate_bpm": heart_rate,
        "hrv_ms": hrv,
        "resting_heart_rate_bpm": resting_rate,
        "activity": activity[:80] or "unspecified",
        "source": source[:80] or "Apple Health Shortcut",
    }
    safe_context = context or {}
    reading["context"] = {
        "active_window": str(safe_context.get("active_window") or "Unknown")[:200],
        "assistant_mode": str(safe_context.get("assistant_mode") or "Normal")[:40],
        "stated_activity": str(safe_context.get("stated_activity") or "")[:120],
    }
    return reading


class HealthStore:
    def __init__(self, path: Path, retention_days: int = 7) -> None:
        self.path = path
        self.retention_days = max(1, min(90, int(retention_days)))
        self._lock = threading.Lock()

    def readings(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_unlocked()

    def latest(self) -> dict[str, Any] | None:
        readings = self.readings()
        return readings[-1] if readings else None

    def append(self, reading: dict[str, Any]) -> None:
        with self._lock:
            readings = self._prune(self._read_unlocked())
            readings.append(reading)
            readings = readings[-MAX_STORED_READINGS:]
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps({"readings": readings}, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def clear(self) -> None:
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def _read_unlocked(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            readings = payload.get("readings", [])
            return [item for item in readings if isinstance(item, dict)] if isinstance(readings, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _prune(self, readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cutoff = dt.datetime.now().astimezone() - dt.timedelta(days=self.retention_days)
        kept: list[dict[str, Any]] = []
        for reading in readings:
            try:
                received = dt.datetime.fromisoformat(str(reading.get("received_at", "")).replace("Z", "+00:00"))
                if received.tzinfo is None:
                    received = received.replace(tzinfo=cutoff.tzinfo)
                if received >= cutoff:
                    kept.append(reading)
            except ValueError:
                continue
        return kept


def assess_health_reading(reading: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, str]:
    """Offer conservative wellness context without diagnosing stress or illness."""
    heart_rate = reading.get("heart_rate_bpm")
    activity = str(reading.get("activity") or "unspecified").lower()
    context = reading.get("context", {}) if isinstance(reading.get("context"), dict) else {}
    window = str(context.get("active_window") or "your current task")
    exercise_terms = ("exercise", "workout", "running", "walking", "cycling", "sports", "gym")
    exercising = any(term in activity for term in exercise_terms)

    baseline_values: list[float] = []
    for item in history[-500:]:
        value = item.get("heart_rate_bpm")
        item_activity = str(item.get("activity") or "").lower()
        if isinstance(value, (int, float)) and 45 <= float(value) <= 110 and not any(term in item_activity for term in exercise_terms):
            baseline_values.append(float(value))
    baseline = median(baseline_values) if len(baseline_values) >= 5 else None

    if heart_rate is None:
        return {
            "level": "info",
            "summary": "Health update received without a current heart-rate sample.",
            "suggestion": "HRV is most useful as a trend. One reading alone cannot establish stress or its cause.",
        }

    bpm = float(heart_rate)
    elevated_threshold = max(110.0, (baseline + 35.0) if baseline is not None else 110.0)
    if exercising:
        return {
            "level": "normal",
            "summary": f"Heart rate {bpm:.0f} BPM while activity is marked as {activity}.",
            "suggestion": "That context can explain an elevated reading. ATLAS will keep it as a trend, not a diagnosis.",
        }
    if bpm >= 150:
        return {
            "level": "urgent_check",
            "summary": f"Heart rate is {bpm:.0f} BPM while no exercise is recorded.",
            "suggestion": "Pause and check how you feel. If you have chest pain, fainting, severe shortness of breath, or feel unsafe, seek urgent medical help now.",
        }
    if bpm >= elevated_threshold:
        baseline_text = f" compared with your recent baseline near {baseline:.0f}" if baseline is not None else ""
        return {
            "level": "elevated",
            "summary": f"Heart rate is {bpm:.0f} BPM{baseline_text} while you appear to be in {window}.",
            "suggestion": "Possible explanations include movement, caffeine, excitement, pain, or stress. Consider pausing, breathing slowly, and telling me what you are doing so I can add context.",
        }
    if bpm <= 45:
        return {
            "level": "low_check",
            "summary": f"Heart rate is {bpm:.0f} BPM.",
            "suggestion": "This can be normal for some people, especially during rest or with athletic conditioning. If it is unusual for you or you feel dizzy, weak, or faint, contact a medical professional.",
        }
    return {
        "level": "normal",
        "summary": f"Latest heart rate is {bpm:.0f} BPM.",
        "suggestion": "No strong conclusion from a single sample. Trends and your stated activity are more useful.",
    }


@dataclass
class HealthBridgeStatus:
    running: bool
    message: str
    url: str


class HealthBridgeServer:
    def __init__(
        self,
        store: HealthStore,
        token: str,
        port: int,
        context_provider: Callable[[], dict[str, Any]],
        on_reading: Callable[[dict[str, Any], dict[str, str]], None],
    ) -> None:
        self.store = store
        self.token = token
        self.port = max(1024, min(65535, int(port)))
        self.context_provider = context_provider
        self.on_reading = on_reading
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.last_error = ""

    @property
    def url(self) -> str:
        return f"http://{local_ipv4_address()}:{self.port}/health"

    def start(self) -> HealthBridgeStatus:
        if self._server is not None:
            return self.status()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path.rstrip("/") != "/status":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                self._reply(200, {"ok": True, "service": "ATLAS Health Bridge"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path.split("?", 1)[0].rstrip("/") != "/health":
                    self._reply(404, {"ok": False, "error": "Not found"})
                    return
                if not is_private_client(self.client_address[0]):
                    self._reply(403, {"ok": False, "error": "Local-network clients only"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    self._reply(413, {"ok": False, "error": "Invalid request size"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._reply(400, {"ok": False, "error": "Invalid JSON"})
                    return
                supplied_token = str(
                    self.headers.get("X-ATLAS-Health-Token")
                    or self.headers.get("X-JARVIS-Health-Token")
                    or payload.pop("token", "")
                )
                if not secrets.compare_digest(supplied_token, bridge.token):
                    self._reply(401, {"ok": False, "error": "Pairing code rejected"})
                    return
                try:
                    context = bridge.context_provider()
                    reading = normalize_health_payload(payload, context)
                    history = bridge.store.readings()
                    assessment = assess_health_reading(reading, history)
                    bridge.store.append(reading)
                    bridge.on_reading(reading, assessment)
                except ValueError as exc:
                    self._reply(400, {"ok": False, "error": str(exc)})
                    return
                except Exception:
                    self._reply(500, {"ok": False, "error": "Health update could not be stored"})
                    return
                self._reply(200, {"ok": True, "assessment": assessment["level"]})

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
            self._thread = threading.Thread(target=self._server.serve_forever, name="jarvis-health-bridge", daemon=True)
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

    def status(self) -> HealthBridgeStatus:
        if self._server is not None:
            return HealthBridgeStatus(True, "Listening on your private network", self.url)
        if self.last_error:
            return HealthBridgeStatus(False, f"Could not start: {self.last_error}", self.url)
        return HealthBridgeStatus(False, "Off", self.url)
