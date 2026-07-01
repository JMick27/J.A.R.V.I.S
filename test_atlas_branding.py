import unittest

import jarvis


class AtlasBrandingTests(unittest.TestCase):
    def test_product_name_and_expansion(self) -> None:
        self.assertEqual(jarvis.APP_NAME, "ATLAS Desktop Assistant")
        self.assertIn("Adaptive Task, Learning & Automation System", jarvis.SYSTEM_PROMPT)

    def test_legacy_default_wake_phrase_migrates(self) -> None:
        merged = jarvis._merge_settings(jarvis.DEFAULT_SETTINGS, {"wake_phrase": "jarvis"})
        self.assertEqual(merged["wake_phrase"], "atlas")

    def test_custom_wake_phrase_is_preserved(self) -> None:
        merged = jarvis._merge_settings(jarvis.DEFAULT_SETTINGS, {"wake_phrase": "computer"})
        self.assertEqual(merged["wake_phrase"], "computer")


if __name__ == "__main__":
    unittest.main()
