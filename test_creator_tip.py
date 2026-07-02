from __future__ import annotations

import datetime as dt
import unittest

import jarvis


class CreatorTipTests(unittest.TestCase):
    def configured_settings(self) -> dict[str, object]:
        return {
            "creator_tip_enabled": True,
            "creator_tip_crypto_name": "Monero",
            "creator_tip_crypto_network": "Monero",
            "creator_tip_address": "public-address",
            "creator_tip_payment_uri": "",
            "creator_tip_chance_denominator": 20,
            "creator_tip_cooldown_hours": 72,
            "creator_tip_last_shown_at": "",
        }

    def test_tip_requires_public_payment_details_and_winning_roll(self) -> None:
        now = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
        settings = self.configured_settings()
        self.assertEqual(jarvis.creator_tip_message(settings, now=now, roll=7), "")
        settings["creator_tip_address"] = ""
        self.assertEqual(jarvis.creator_tip_message(settings, now=now, roll=0), "")

    def test_tip_uses_one_in_twenty_roll_and_persists_cooldown(self) -> None:
        now = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
        settings = self.configured_settings()
        message = jarvis.creator_tip_message(settings, now=now, roll=0)
        self.assertIn("optional tip", message)
        self.assertIn("public-address", message)
        self.assertTrue(settings["creator_tip_last_shown_at"])
        self.assertEqual(
            jarvis.creator_tip_message(settings, now=now + dt.timedelta(hours=71), roll=0),
            "",
        )
        self.assertTrue(
            jarvis.creator_tip_message(settings, now=now + dt.timedelta(hours=72), roll=0)
        )

    def test_payment_uri_is_preferred_when_configured(self) -> None:
        settings = self.configured_settings()
        settings["creator_tip_payment_uri"] = "monero:public-address"
        message = jarvis.creator_tip_message(
            settings,
            now=dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc),
            roll=0,
        )
        self.assertIn("monero:public-address", message)

    def test_public_release_uses_configured_litecoin_receive_address(self) -> None:
        self.assertEqual(
            jarvis.DEFAULT_SETTINGS["creator_tip_address"],
            "ltc1qzwzah5z0sqjp8pvfazd7q3hetwx3ktqmcetcy4",
        )
        self.assertEqual(
            jarvis.DEFAULT_SETTINGS["creator_tip_payment_uri"],
            "litecoin:ltc1qzwzah5z0sqjp8pvfazd7q3hetwx3ktqmcetcy4",
        )


if __name__ == "__main__":
    unittest.main()
