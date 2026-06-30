import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jarvis


class _FakeMusic:
    def __init__(self) -> None:
        self.loaded = ""
        self.busy = False
        self.volume = 0.0

    def load(self, path: str) -> None:
        self.loaded = path

    def play(self) -> None:
        self.busy = True

    def stop(self) -> None:
        self.busy = False

    def pause(self) -> None:
        self.busy = False

    def unpause(self) -> None:
        self.busy = True

    def set_volume(self, value: float) -> None:
        self.volume = value

    def get_busy(self) -> bool:
        return self.busy


class _FakeMixer:
    def __init__(self) -> None:
        self.music = _FakeMusic()

    def init(self) -> None:
        return None

    def quit(self) -> None:
        return None


class LocalMusicPlayerTests(unittest.TestCase):
    def test_discovers_supported_audio_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "album").mkdir()
            (root / "song.mp3").write_bytes(b"audio")
            (root / "album" / "track.ogg").write_bytes(b"audio")
            (root / "notes.txt").write_text("not music", encoding="utf-8")
            found = jarvis.discover_local_audio_files(root)
            self.assertEqual({Path(path).name for path in found}, {"song.mp3", "track.ogg"})

    def test_clean_paths_removes_duplicates_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            song = Path(temp) / "song.wav"
            song.write_bytes(b"audio")
            cleaned = jarvis.clean_local_music_paths([str(song), str(song), str(Path(temp) / "missing.mp3")])
            self.assertEqual(cleaned, [str(song.resolve())])

    def test_queue_plays_and_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.mp3"
            second = Path(temp) / "second.mp3"
            first.write_bytes(b"audio")
            second.write_bytes(b"audio")
            fake_mixer = _FakeMixer()
            with patch.object(jarvis, "pygame", SimpleNamespace(mixer=fake_mixer)):
                player = jarvis.LocalMusicPlayer(0.5)
                ok, title = player.play_queue([str(first), str(second)])
                self.assertTrue(ok)
                self.assertEqual(title, "first")
                self.assertEqual(fake_mixer.music.volume, 0.5)
                ok, title = player.next()
                self.assertTrue(ok)
                self.assertEqual(title, "second")


if __name__ == "__main__":
    unittest.main()
