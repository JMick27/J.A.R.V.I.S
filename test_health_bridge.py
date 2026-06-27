import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from health_bridge import (
    HealthStore,
    assess_health_reading,
    is_private_client,
    load_or_create_pairing_token,
    normalize_health_payload,
)


class HealthBridgeTests(unittest.TestCase):
    def test_pairing_token_is_created_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "token.txt"
            first = load_or_create_pairing_token(path)
            second = load_or_create_pairing_token(path)
            self.assertEqual(first, second)
            self.assertGreaterEqual(len(first), 24)

    def test_payload_validation_accepts_aliases_and_rejects_empty(self) -> None:
        reading = normalize_health_payload(
            {"heart_rate": "82 count/min", "hrv": "41 ms", "activity": "coding"},
            {"active_window": "Visual Studio Code", "assistant_mode": "Coding"},
        )
        self.assertEqual(reading["heart_rate_bpm"], 82.0)
        self.assertEqual(reading["hrv_ms"], 41.0)
        self.assertEqual(reading["activity"], "coding")
        self.assertEqual(reading["context"]["active_window"], "Visual Studio Code")
        with self.assertRaises(ValueError):
            normalize_health_payload({}, {})
        with self.assertRaises(ValueError):
            normalize_health_payload({"heart_rate": 500}, {})

    def test_store_prunes_old_readings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "health.json"
            old = (dt.datetime.now().astimezone() - dt.timedelta(days=3)).isoformat(timespec="seconds")
            path.write_text(json.dumps({"readings": [{"received_at": old, "heart_rate_bpm": 70}]}), encoding="utf-8")
            store = HealthStore(path, retention_days=1)
            store.append(normalize_health_payload({"heart_rate": 80}, {}))
            readings = store.readings()
            self.assertEqual(len(readings), 1)
            self.assertEqual(readings[0]["heart_rate_bpm"], 80.0)

    def test_health_assessment_respects_exercise_context(self) -> None:
        history = [
            {"heart_rate_bpm": 70, "activity": "resting"},
            {"heart_rate_bpm": 72, "activity": "coding"},
            {"heart_rate_bpm": 68, "activity": "studying"},
            {"heart_rate_bpm": 73, "activity": "gaming"},
            {"heart_rate_bpm": 71, "activity": "writing"},
        ]
        elevated = assess_health_reading({"heart_rate_bpm": 122, "activity": "coding", "context": {"active_window": "Docs"}}, history)
        exercise = assess_health_reading({"heart_rate_bpm": 122, "activity": "running", "context": {"active_window": "Maps"}}, history)
        self.assertEqual(elevated["level"], "elevated")
        self.assertEqual(exercise["level"], "normal")

    def test_private_client_filter(self) -> None:
        self.assertTrue(is_private_client("127.0.0.1"))
        self.assertTrue(is_private_client("192.168.1.15"))
        self.assertFalse(is_private_client("8.8.8.8"))


if __name__ == "__main__":
    unittest.main()
