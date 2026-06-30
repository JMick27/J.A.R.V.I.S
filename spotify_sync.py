from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

try:
    import win32crypt
except Exception:
    win32crypt = None


SPOTIFY_SCOPES = "playlist-read-private playlist-read-collaborative user-library-read"


class SpotifySyncError(RuntimeError):
    pass


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class SpotifyTokenStore:
    """Store OAuth tokens encrypted for the current Windows account."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, token: dict[str, Any]) -> None:
        if win32crypt is None:
            raise SpotifySyncError("Windows token encryption is unavailable.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(token).encode("utf-8")
        encrypted = win32crypt.CryptProtectData(raw, "JARVIS Spotify", None, None, None, 0)[1]
        self.path.write_bytes(base64.b64encode(encrypted))

    def load(self) -> dict[str, Any] | None:
        if win32crypt is None or not self.path.exists():
            return None
        try:
            encrypted = base64.b64decode(self.path.read_bytes())
            raw = win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1]
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


class _OAuthCallbackServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int]) -> None:
        self.result: dict[str, str] = {}
        self.event = threading.Event()
        super().__init__(address, _OAuthCallbackHandler)


class _OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        server = self.server
        if isinstance(server, _OAuthCallbackServer):
            server.result = {key: values[0] for key, values in query.items() if values}
            server.event.set()
        body = (
            "<html><body style='background:#030712;color:#d9f7ff;font-family:Segoe UI;padding:40px'>"
            "<h1>Spotify connected to J.A.R.V.I.S.</h1><p>You may close this tab and return to JARVIS.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class SpotifyLibraryClient:
    def __init__(self, client_id: str, token_path: Path, redirect_port: int = 8767) -> None:
        self.client_id = client_id.strip()
        self.redirect_port = int(redirect_port)
        self.redirect_uri = f"http://127.0.0.1:{self.redirect_port}/callback"
        self.tokens = SpotifyTokenStore(token_path)
        self.session = requests.Session()

    def connect(self, timeout_seconds: int = 180) -> dict[str, Any]:
        if not self.client_id:
            raise SpotifySyncError("Add a Spotify Client ID first.")
        verifier = secrets.token_urlsafe(64)
        state = secrets.token_urlsafe(24)
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": SPOTIFY_SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": _pkce_challenge(verifier),
            "state": state,
        }
        try:
            server = _OAuthCallbackServer(("127.0.0.1", self.redirect_port))
        except OSError as exc:
            raise SpotifySyncError(f"Spotify callback port {self.redirect_port} is unavailable: {exc}") from exc
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        webbrowser.open(f"https://accounts.spotify.com/authorize?{urlencode(params)}")
        if not server.event.wait(timeout_seconds):
            server.shutdown()
            server.server_close()
            raise SpotifySyncError("Spotify sign-in timed out.")
        result = dict(server.result)
        server.shutdown()
        server.server_close()
        if result.get("state") != state:
            raise SpotifySyncError("Spotify returned an invalid authorization state.")
        if result.get("error"):
            raise SpotifySyncError(f"Spotify authorization was declined: {result['error']}")
        code = result.get("code", "")
        if not code:
            raise SpotifySyncError("Spotify did not return an authorization code.")
        response = self.session.post(
            "https://accounts.spotify.com/api/token",
            data={
                "client_id": self.client_id,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": verifier,
            },
            timeout=20,
        )
        if not response.ok:
            raise SpotifySyncError(f"Spotify token exchange failed ({response.status_code}).")
        token = response.json()
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600)) - 60
        self.tokens.save(token)
        return token

    def disconnect(self) -> None:
        self.tokens.clear()

    def _token(self) -> dict[str, Any]:
        token = self.tokens.load()
        if not token:
            raise SpotifySyncError("Spotify is not connected.")
        if float(token.get("expires_at", 0)) > time.time():
            return token
        refresh_token = str(token.get("refresh_token", ""))
        if not refresh_token:
            raise SpotifySyncError("Spotify authorization expired. Connect again.")
        response = self.session.post(
            "https://accounts.spotify.com/api/token",
            data={"client_id": self.client_id, "grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=20,
        )
        if not response.ok:
            raise SpotifySyncError(f"Spotify token refresh failed ({response.status_code}).")
        refreshed = response.json()
        refreshed["refresh_token"] = refreshed.get("refresh_token") or refresh_token
        refreshed["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600)) - 60
        self.tokens.save(refreshed)
        return refreshed

    def _get(self, url: str) -> dict[str, Any]:
        token = self._token()
        response = self.session.get(url, headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=20)
        if not response.ok:
            detail = response.json().get("error", {}).get("message", "request failed") if response.content else "request failed"
            raise SpotifySyncError(f"Spotify API error {response.status_code}: {detail}")
        data = response.json()
        return data if isinstance(data, dict) else {}

    def _paged_items(self, url: str, maximum: int = 1000) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url = url
        while next_url and len(items) < maximum:
            page = self._get(next_url)
            items.extend(item for item in page.get("items", []) if isinstance(item, dict))
            next_url = str(page.get("next") or "")
        return items[:maximum]

    def sync(self) -> dict[str, Any]:
        profile = self._get("https://api.spotify.com/v1/me")
        playlist_rows = self._paged_items("https://api.spotify.com/v1/me/playlists?limit=50")
        saved_rows = self._paged_items("https://api.spotify.com/v1/me/tracks?limit=50")
        playlists = [
            {
                "name": str(item.get("name", "Untitled Playlist")),
                "uri": str(item.get("uri", "")),
                "url": str(item.get("external_urls", {}).get("spotify", "")),
                "tracks": int(item.get("tracks", {}).get("total", 0) or 0),
            }
            for item in playlist_rows
            if item.get("uri")
        ]
        tracks: list[dict[str, str]] = []
        for row in saved_rows:
            track = row.get("track", {})
            if not isinstance(track, dict) or not track.get("uri"):
                continue
            artists = ", ".join(str(artist.get("name", "")) for artist in track.get("artists", []) if isinstance(artist, dict))
            tracks.append(
                {
                    "name": str(track.get("name", "Unknown Track")),
                    "artist": artists,
                    "uri": str(track.get("uri", "")),
                    "url": str(track.get("external_urls", {}).get("spotify", "")),
                }
            )
        return {
            "profile": {"id": str(profile.get("id", "")), "name": str(profile.get("display_name") or profile.get("id") or "Spotify User")},
            "playlists": playlists,
            "tracks": tracks,
            "synced_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
