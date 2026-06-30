import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import spotify_sync


class _FakeCrypt:
    @staticmethod
    def CryptProtectData(data, *_args):
        return None, b"protected:" + data

    @staticmethod
    def CryptUnprotectData(data, *_args):
        return None, data.removeprefix(b"protected:")


class SpotifySyncTests(unittest.TestCase):
    def test_pkce_challenge_is_url_safe(self) -> None:
        challenge = spotify_sync._pkce_challenge("a" * 64)
        self.assertNotIn("=", challenge)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)

    def test_token_store_round_trip_uses_encryption(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch.object(spotify_sync, "win32crypt", _FakeCrypt):
            path = Path(temp) / "token.dat"
            store = spotify_sync.SpotifyTokenStore(path)
            store.save({"access_token": "private-token", "expires_at": 123})
            self.assertNotIn(b"private-token", path.read_bytes())
            self.assertEqual(store.load()["access_token"], "private-token")
            store.clear()
            self.assertFalse(path.exists())

    def test_sync_normalizes_playlists_and_saved_tracks(self) -> None:
        client = spotify_sync.SpotifyLibraryClient("client", Path("unused-token.dat"))
        client._get = lambda _url: {"id": "user", "display_name": "Jackson"}

        def pages(url: str, maximum: int = 1000):
            if "playlists" in url:
                return [{"name": "Road Trip", "uri": "spotify:playlist:1", "external_urls": {"spotify": "https://open.spotify.com/playlist/1"}, "tracks": {"total": 12}}]
            return [{"track": {"name": "One", "uri": "spotify:track:1", "external_urls": {"spotify": "https://open.spotify.com/track/1"}, "artists": [{"name": "Metallica"}]}}]

        client._paged_items = pages
        result = client.sync()
        self.assertEqual(result["profile"]["name"], "Jackson")
        self.assertEqual(result["playlists"][0]["tracks"], 12)
        self.assertEqual(result["tracks"][0]["artist"], "Metallica")


if __name__ == "__main__":
    unittest.main()
