from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import jarvis
import atlas_coding


class CodingWorkspaceTests(unittest.TestCase):
    def test_coding_engine_creates_saves_and_reversibly_deletes_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = atlas_coding.create_script(root, "scripts/player.gd", "extends Node\n")
            original_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            _saved, backup = atlas_coding.save_script(
                root,
                "scripts/player.gd",
                "extends CharacterBody2D\n",
                original_hash,
            )
            self.assertTrue(backup.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "extends CharacterBody2D\n")
            trash = atlas_coding.delete_script(root, "scripts/player.gd")
            self.assertFalse(target.exists())
            self.assertTrue(trash.exists())
            self.assertIn(".atlas_trash", trash.parts)

    def test_coding_engine_confines_all_paths_to_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            with self.assertRaises(ValueError):
                atlas_coding.create_script(root, "../outside.py", "")
            with self.assertRaises(ValueError):
                atlas_coding.create_script(root, ".git/config", "")

    def test_coding_engine_detects_godot_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.godot").write_text("[application]\nconfig/name=\"Demo\"\n", encoding="utf-8")
            details = atlas_coding.detect_project(root)
            self.assertEqual(details["type"], "Godot")
            self.assertIn("project.godot", details["settings_files"])

    def test_search_finds_filename_and_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alpha.py").write_text("class ReactorCore:\n    pass\n", encoding="utf-8")
            by_name = jarvis.coding_workspace_files(root, query="alpha")
            by_content = jarvis.coding_workspace_files(root, query="ReactorCore")
            self.assertEqual([path.name for path in by_name], ["alpha.py"])
            self.assertEqual([path.name for path in by_content], ["alpha.py"])

    def test_edit_creates_backup_and_rejects_stale_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "demo.py"
            target.write_text("value = 1\n", encoding="utf-8")
            original = target.read_bytes()
            expected_hash = hashlib.sha256(original).hexdigest()
            ok, _message, backup = jarvis.apply_code_edit_with_backup(
                root,
                target,
                "value = 2\n",
                expected_hash,
                "\n",
            )
            self.assertTrue(ok)
            self.assertIsNotNone(backup)
            self.assertTrue(backup and backup.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")

            stale_ok, stale_message, _backup = jarvis.apply_code_edit_with_backup(
                root,
                target,
                "value = 3\n",
                expected_hash,
                "\n",
            )
            self.assertFalse(stale_ok)
            self.assertIn("changed", stale_message.lower())

    def test_diagnostics_report_supported_syntax_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "requirements.txt").write_text("", encoding="utf-8")
            (root / "good.py").write_text("value = 1\n", encoding="utf-8")
            (root / "bad.py").write_text("def broken(:\n    pass\n", encoding="utf-8")
            (root / "bad.json").write_text('{"value": }', encoding="utf-8")
            (root / "conflict.js").write_text(
                "<<<<<<< HEAD\nleft\n=======\nright\n>>>>>>> branch\n",
                encoding="utf-8",
            )
            report = jarvis.diagnose_coding_workspace(root)
            issue_files = {issue["file"] for issue in report["issues"]}
            self.assertEqual(report["project_type"], "Python")
            self.assertIn("bad.py", issue_files)
            self.assertIn("bad.json", issue_files)
            self.assertIn("conflict.js", issue_files)
            self.assertNotIn("good.py", issue_files)

    def test_agent_code_reads_block_and_redact_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text('API_KEY = "private-value"\n', encoding="utf-8")
            (root / "config.json").write_text('{"access_token":"private-token"}', encoding="utf-8")
            (root / ".env").write_text("GEMINI_API_KEY=never-send\n", encoding="utf-8")
            assistant = SimpleNamespace(
                settings={"coding_workspace_folder": str(root), "coding_workspace_max_files": 100},
                current_mode="Normal",
            )
            registry = jarvis.ToolRegistry(assistant)
            python_read = registry._read_code_file({"path": "demo.py"})
            json_read = registry._read_code_file({"path": "config.json"})
            env_read = registry._read_code_file({"path": ".env"})
            self.assertNotIn("private-value", python_read)
            self.assertNotIn("private-token", json_read)
            self.assertIn("[REDACTED]", python_read)
            self.assertIn("[REDACTED]", json_read)
            self.assertIn("blocked", env_read.lower())
            self.assertNotIn("never-send", env_read)

    def test_runner_registry_rejects_unknown_ids_and_safe_mode_overrides_full_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("value = 1\n", encoding="utf-8")
            (root / "test_demo.py").write_text(
                "import unittest\n\nclass DemoTest(unittest.TestCase):\n"
                "    def test_value(self):\n        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )
            runner_ids = {runner["id"] for runner in jarvis.approved_code_runners(root)}
            self.assertIn("python_compile", runner_ids)
            self.assertIn("python_unittest", runner_ids)
            rejected = jarvis.run_approved_code_runner(root, "not_a_real_runner", timeout_seconds=10)
            self.assertFalse(rejected["ok"])

            assistant = SimpleNamespace(
                settings={"agent_permission_mode": "Full access"},
                current_mode="Safe",
            )
            registry = jarvis.ToolRegistry(assistant)
            tool = registry.tools["run_code_check"]
            call = {"action": "run_code_check", "args": {"runner_id": "python_unittest"}, "risk": "high"}
            self.assertTrue(registry.requires_confirmation(call, tool))


if __name__ == "__main__":
    unittest.main()
