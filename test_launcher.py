import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from launcher import APP_EXE, APP_FOLDER, version_tuple


class LauncherTests(unittest.TestCase):
    def test_version_comparison(self) -> None:
        self.assertGreater(version_tuple("v1.2.0"), version_tuple("1.1.9"))
        self.assertEqual(version_tuple("v0.1.0"), (0, 1, 0))

    def test_install_names_remain_stable(self) -> None:
        self.assertEqual(APP_FOLDER, "JARVIS Desktop Assistant")
        self.assertEqual(APP_EXE, "JARVIS Desktop Assistant.exe")

    def test_release_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            archive = Path(temp_name) / "app.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("JARVIS Desktop Assistant.exe", b"test")
            first = hashlib.sha256(archive.read_bytes()).hexdigest()
            second = hashlib.sha256(archive.read_bytes()).hexdigest()
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
