import unittest
from pathlib import Path

from jarvis import DEFAULT_PERSONALITY, DEFAULT_SETTINGS
from jarvis import SYSTEM_PROMPT


class PrivacyDefaultTests(unittest.TestCase):
    def test_new_profiles_have_no_bundled_user_identity(self) -> None:
        self.assertEqual(DEFAULT_SETTINGS["user_name"], "")
        self.assertFalse(DEFAULT_SETTINGS["profile_initialized"])
        self.assertEqual(DEFAULT_PERSONALITY["user_name"], "")
        self.assertEqual(DEFAULT_PERSONALITY["startup_greeting_name"], "")

    def test_source_has_no_developer_windows_path(self) -> None:
        project = Path(__file__).resolve().parent
        checked = [project / "jarvis.py", project / "README.md", project / "config.example.env"]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in checked)
        self.assertNotIn(r"C:\Users\jacks", combined)
        self.assertNotIn("helping Jackson revise", combined)

    def test_system_prompt_requires_grounded_self_awareness(self) -> None:
        normalized_prompt = " ".join(SYSTEM_PROMPT.lower().split())
        self.assertIn("operational self-awareness", normalized_prompt)
        self.assertIn("label it as fictional", normalized_prompt)

    def test_retired_welcome_screen_is_not_in_source(self) -> None:
        source = (Path(__file__).resolve().parent / "jarvis.py").read_text(encoding="utf-8")
        self.assertNotIn("welcome_screen_enabled", source)
        self.assertNotIn("_show_welcome_screen", source)


if __name__ == "__main__":
    unittest.main()
