"""Project-safe services for the A.T.L.A.S Coding Engine.

This module deliberately exposes project operations instead of a shell.  Every
path is confined to the selected workspace and destructive operations are
reversible through the local .atlas_trash directory.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import psutil


ENGINE_MARKERS = {
    "Godot": ("project.godot",),
    "Unity": ("ProjectSettings/ProjectVersion.txt",),
    "Unreal Engine": ("*.uproject",),
}

SETTINGS_FILES = {
    "Godot": ("project.godot",),
    "Unity": ("ProjectSettings/ProjectSettings.asset", "Packages/manifest.json"),
    "Unreal Engine": ("Config/DefaultEngine.ini", "Config/DefaultGame.ini"),
    "Python": ("pyproject.toml", "setup.cfg", "requirements.txt"),
    "Node.js": ("package.json", "tsconfig.json"),
    ".NET": ("Directory.Build.props",),
}


def project_path(root: Path, relative: str | Path, *, must_exist: bool = False) -> Path:
    """Resolve a path inside root and reject traversal, links, and internals."""
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        rel = candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("Path is outside the selected project.") from exc
    if rel.parts and rel.parts[0].lower() in {".git", ".atlas_trash", ".jarvis_backups"}:
        raise ValueError("That internal project folder is protected.")
    if must_exist and not candidate.exists():
        raise FileNotFoundError(candidate)
    return candidate


def create_script(root: Path, relative: str, content: str = "") -> Path:
    target = project_path(root, relative)
    if target.exists():
        raise FileExistsError(f"{relative} already exists.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="")
    return target


def save_script(root: Path, relative: str, content: str, expected_hash: str = "") -> tuple[Path, Path]:
    target = project_path(root, relative, must_exist=True)
    if not target.is_file():
        raise ValueError("The selected item is not a file.")
    original = target.read_bytes()
    if expected_hash and hashlib.sha256(original).hexdigest() != expected_hash:
        raise RuntimeError("The file changed outside A.T.L.A.S. Reload it before saving.")
    backup_root = root.resolve() / ".jarvis_backups"
    if backup_root.exists() and backup_root.is_symlink():
        raise ValueError("The backup folder is a symbolic link.")
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / target.relative_to(root.resolve())
    backup.parent.mkdir(parents=True, exist_ok=True)
    try:
        backup.parent.resolve().relative_to(backup_root.resolve())
    except ValueError as exc:
        raise ValueError("The backup destination leaves the project backup folder.") from exc
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = backup.with_name(f"{backup.name}.{stamp}.bak")
    shutil.copy2(target, backup)
    temp = target.with_name(f".{target.name}.{stamp}.atlas.tmp")
    try:
        temp.write_text(content, encoding="utf-8", newline="")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target, backup


def delete_script(root: Path, relative: str) -> Path:
    """Move a project file to reversible local trash; never permanently delete."""
    target = project_path(root, relative, must_exist=True)
    if not target.is_file():
        raise ValueError("Only files can be removed from the Coding Engine.")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    trash_root = root.resolve() / ".atlas_trash"
    if trash_root.exists() and trash_root.is_symlink():
        raise ValueError("The project trash folder is a symbolic link.")
    trash_root.mkdir(parents=True, exist_ok=True)
    trash = trash_root / stamp / target.relative_to(root.resolve())
    trash.parent.mkdir(parents=True, exist_ok=True)
    try:
        trash.parent.resolve().relative_to(trash_root.resolve())
    except ValueError as exc:
        raise ValueError("The trash destination leaves the project trash folder.") from exc
    shutil.move(str(target), str(trash))
    return trash


def detect_project(root: Path) -> dict[str, Any]:
    root = root.resolve()
    project_type = "General source project"
    for engine, markers in ENGINE_MARKERS.items():
        if any((root / marker).exists() if "*" not in marker else any(root.glob(marker)) for marker in markers):
            project_type = engine
            break
    if project_type == "General source project":
        if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
            project_type = "Python"
        elif (root / "package.json").exists():
            project_type = "Node.js"
        elif any(root.glob("*.sln")) or any(root.glob("*.csproj")):
            project_type = ".NET"

    settings = []
    for relative in SETTINGS_FILES.get(project_type, ()):
        if (root / relative).is_file():
            settings.append(relative)
    engine = find_project_engine(root, project_type)
    return {
        "name": root.name,
        "type": project_type,
        "settings_files": settings,
        "engine_running": bool(engine),
        "engine_process": engine,
    }


def find_project_engine(root: Path, project_type: str) -> dict[str, Any] | None:
    names = {
        "Godot": {"godot.exe", "godot_mono.exe", "godot"},
        "Unity": {"unity.exe", "unity"},
        "Unreal Engine": {"unrealeditor.exe", "ue4editor.exe"},
    }.get(project_type, set())
    if not names:
        return None
    root_text = str(root.resolve()).lower()
    fallback: dict[str, Any] | None = None
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            if str(proc.info.get("name") or "").lower() not in names:
                continue
            info = {"pid": proc.pid, "name": proc.info.get("name") or project_type, "exe": proc.info.get("exe") or ""}
            command = " ".join(str(item) for item in (proc.info.get("cmdline") or [])).lower()
            if root_text in command:
                return info
            fallback = fallback or info
        except (psutil.Error, OSError):
            continue
    return fallback


def launch_project_engine(root: Path, project_type: str) -> tuple[bool, str]:
    root = root.resolve()
    if project_type == "Godot":
        marker = root / "project.godot"
        if not marker.exists():
            return False, "This folder does not contain project.godot."
        candidates = [shutil.which(name) for name in ("godot.exe", "godot4.exe", "godot", "godot4")]
        executable = next((item for item in candidates if item), None)
        try:
            if executable:
                subprocess.Popen([executable, "--editor", "--path", str(root)], cwd=root, shell=False)
            else:
                os.startfile(str(marker))
            return True, "Godot project launch requested."
        except OSError as exc:
            return False, f"Could not launch Godot: {exc}"
    if project_type == "Unity":
        try:
            os.startfile(str(root))
            return True, "Unity project folder opened. Use Unity Hub to add or launch it."
        except OSError as exc:
            return False, f"Could not open the Unity project: {exc}"
    if project_type == "Unreal Engine":
        project = next(root.glob("*.uproject"), None)
        if project:
            try:
                os.startfile(str(project))
                return True, "Unreal project launch requested."
            except OSError as exc:
                return False, f"Could not launch Unreal Editor: {exc}"
    return False, "No supported game engine was detected for this project."


def focus_engine_window(project_type: str) -> bool:
    """Bring an open engine window forward using the Win32 window API."""
    if os.name != "nt":
        return False
    import ctypes
    import ctypes.wintypes

    terms = {
        "Godot": ("godot",),
        "Unity": ("unity",),
        "Unreal Engine": ("unreal editor", "ue4editor"),
    }.get(project_type, ())
    found: list[int] = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def enum_window(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        if any(term in title.value.lower() for term in terms):
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(enum_window, 0)
    if not found:
        return False
    user32.ShowWindow(found[0], 9)
    return bool(user32.SetForegroundWindow(found[0]))


def suggested_script_template(project_type: str, filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_]", "_", Path(filename).stem)
    suffix = Path(filename).suffix.lower()
    if project_type == "Godot" or suffix == ".gd":
        return "extends Node\n\n\nfunc _ready() -> void:\n    pass\n"
    if suffix in {".py", ".pyw"}:
        return f'"""{stem.replace("_", " ").title()}."""\n\n\ndef main() -> None:\n    pass\n\n\nif __name__ == "__main__":\n    main()\n'
    if suffix in {".js", ".ts"}:
        return "export function main() {\n  // Implementation\n}\n"
    if suffix == ".cs":
        class_name = "".join(part.title() for part in stem.split("_")) or "NewScript"
        return f"public class {class_name}\n{{\n}}\n"
    return ""
