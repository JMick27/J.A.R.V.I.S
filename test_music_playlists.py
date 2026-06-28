import unittest

from jarvis import _normalized_music_label, extract_apple_music_playlist_name


class AppleMusicPlaylistParsingTests(unittest.TestCase):
    def test_named_playlist_before_service(self) -> None:
        self.assertEqual(
            extract_apple_music_playlist_name("play jackson's playlist on apple music"),
            "jackson's playlist",
        )

    def test_library_wording(self) -> None:
        self.assertEqual(
            extract_apple_music_playlist_name("Jarvis, play my workout playlist from my Apple Music library"),
            "workout playlist",
        )

    def test_playlist_name_after_keyword(self) -> None:
        self.assertEqual(
            extract_apple_music_playlist_name("play playlist Road Trip on Apple Music"),
            "Road Trip",
        )

    def test_song_request_is_not_a_playlist(self) -> None:
        self.assertIsNone(extract_apple_music_playlist_name("play Master of Puppets on Apple Music"))

    def test_polite_playlist_request(self) -> None:
        self.assertEqual(
            extract_apple_music_playlist_name("Could you play Jackson's playlist on Apple Music?"),
            "Jackson's playlist",
        )

    def test_apostrophes_do_not_break_matching(self) -> None:
        self.assertEqual(_normalized_music_label("Jackson's Playlist"), "jackson s playlist")


if __name__ == "__main__":
    unittest.main()
