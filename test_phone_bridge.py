import tempfile
import unittest
from pathlib import Path

from phone_bridge import PhoneActionQueue, load_or_create_phone_token


class PhoneBridgeTests(unittest.TestCase):
    def test_phone_token_is_created_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "phone-token.txt"
            first = load_or_create_phone_token(path)
            second = load_or_create_phone_token(path)
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 24)

    def test_queue_returns_actions_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = PhoneActionQueue(Path(tmp) / "actions.json")
            item = queue.enqueue("play_apple_music", {"query": "Bad by Michael Jackson"})
            self.assertEqual(queue.pending_count(), 1)
            popped = queue.pop_next()
            self.assertIsNotNone(popped)
            self.assertEqual(popped["id"], item["id"])
            self.assertEqual(popped["action"], "play_apple_music")
            self.assertEqual(popped["payload"]["query"], "Bad by Michael Jackson")
            self.assertEqual(queue.pending_count(), 0)
            self.assertIsNone(queue.pop_next())


if __name__ == "__main__":
    unittest.main()
