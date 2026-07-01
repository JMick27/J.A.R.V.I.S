"""ATLAS Launcher: installs, verifies, updates, rolls back, and launches ATLAS."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import winreg
except ImportError:
    winreg = None


REPOSITORY = "JMick27/J.A.R.V.I.S"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
APP_FOLDER = "JARVIS Desktop Assistant"
APP_EXE = "JARVIS Desktop Assistant.exe"
ZIP_ASSET = "JARVIS-win-x64.zip"
MANIFEST_ASSET = "release-manifest.json"
MANAGED_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_FOLDER
MANAGED_LAUNCHER_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "JARVIS Launcher"
LAUNCHER_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
NEARBY_INSTALL_DIR = LAUNCHER_DIR / APP_FOLDER
# A launcher shipped beside an existing ATLAS updates that exact installation.
# A standalone downloaded launcher uses the normal per-user Programs folder.
INSTALL_DIR = NEARBY_INSTALL_DIR if (NEARBY_INSTALL_DIR / APP_EXE).exists() else MANAGED_INSTALL_DIR
LOCAL_VERSION_FILE = INSTALL_DIR / "version.json"
PREREQUISITES = {
    "edge": {
        "label": "Microsoft Edge (embedded browser and video panels)",
        "winget_id": "Microsoft.Edge",
    },
    "vcredist": {
        "label": "Microsoft Visual C++ Runtime (native audio and vision components)",
        "winget_id": "Microsoft.VCRedist.2015+.x64",
    },
}


def version_tuple(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lower().lstrip("v")
    return tuple(int(part) for part in cleaned.split(".") if part.isdigit()) or (0,)


def edge_installed() -> bool:
    roots = [
        os.environ.get("PROGRAMFILES(X86)", ""),
        os.environ.get("PROGRAMFILES", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    return any(
        root and (Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe").exists()
        for root in roots
    )


def vcredist_installed() -> bool:
    if winreg is None:
        return False
    paths = [
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
    ]
    for path in paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                installed, _kind = winreg.QueryValueEx(key, "Installed")
                if int(installed) == 1:
                    return True
        except (FileNotFoundError, OSError, ValueError):
            continue
    return False


def missing_prerequisites() -> list[str]:
    missing: list[str] = []
    if not edge_installed():
        missing.append("edge")
    if not vcredist_installed():
        missing.append("vcredist")
    return missing


class JarvisLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ATLAS Launcher")
        self.geometry("640x410")
        self.minsize(540, 360)
        self.configure(bg="#030712")
        self.remote_release: dict | None = None
        self.prerequisites_to_install: list[str] = []
        self.prerequisites_only = False
        self._build_ui()
        self.after(250, self.check_for_updates)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Jarvis.Horizontal.TProgressbar", troughcolor="#07111f", background="#38bdf8")

        tk.Label(self, text="A.T.L.A.S.", bg="#030712", fg="#76e4ff", font=("Segoe UI", 32, "bold")).pack(pady=(36, 2))
        tk.Label(self, text="ADAPTIVE TASK, LEARNING & AUTOMATION SYSTEM", bg="#030712", fg="#8fb7c8", font=("Segoe UI", 9)).pack()
        self.status = tk.Label(self, text="Checking systems...", bg="#030712", fg="#e6fbff", font=("Segoe UI", 13))
        self.status.pack(pady=(36, 12))
        self.progress = ttk.Progressbar(self, style="Jarvis.Horizontal.TProgressbar", mode="determinate", maximum=100, length=460)
        self.progress.pack()
        self.detail = tk.Label(self, text="", bg="#030712", fg="#8fb7c8", wraplength=520, justify="center", font=("Segoe UI", 9))
        self.detail.pack(pady=12)

        buttons = tk.Frame(self, bg="#030712")
        buttons.pack(side="bottom", pady=32)
        self.launch_button = tk.Button(buttons, text="LAUNCH ATLAS", command=self.launch, state="disabled", bg="#0d2236", fg="#e6fbff", activebackground="#12384f", activeforeground="#ffffff", relief="flat", padx=26, pady=10)
        self.launch_button.pack(side="left", padx=8)
        self.update_button = tk.Button(buttons, text="INSTALL UPDATE", command=self.install_update, state="disabled", bg="#075985", fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff", relief="flat", padx=26, pady=10)
        self.update_button.pack(side="left", padx=8)

    def ui(self, status: str, detail: str = "", progress: float | None = None) -> None:
        self.after(0, lambda: self.status.config(text=status))
        self.after(0, lambda: self.detail.config(text=detail))
        if progress is not None:
            self.after(0, lambda: self.progress.config(value=max(0, min(100, progress))))

    def local_version(self) -> str:
        try:
            return str(json.loads(LOCAL_VERSION_FILE.read_text(encoding="utf-8")).get("version", "0.0.0"))
        except (OSError, ValueError, TypeError):
            return "0.0.0"

    def check_for_updates(self) -> None:
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self) -> None:
        self.ui("Checking for updates...", "Contacting the ATLAS release channel.", 8)
        try:
            request = urllib.request.Request(RELEASE_API, headers={"User-Agent": "ATLAS-Launcher/0.1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                release = json.load(response)
            self.remote_release = release
            remote = str(release.get("tag_name", "0.0.0")).lstrip("v")
            local = self.local_version()
            installed = (INSTALL_DIR / APP_EXE).exists()
            missing = missing_prerequisites()
            if not installed or version_tuple(remote) > version_tuple(local):
                label = "Installation ready" if not installed else "Update available"
                prerequisite_note = f" {len(missing)} Microsoft prerequisite(s) also need attention." if missing else ""
                self.ui(label, f"Version {remote} is ready. Installed version: {local}.{prerequisite_note}", 18)
                self.after(0, lambda: self.update_button.config(state="normal", text="INSTALL" if not installed else "INSTALL UPDATE"))
                self.prerequisites_only = False
            elif missing:
                self.prerequisites_only = True
                self.ui("Requirements needed", f"ATLAS is current, but {len(missing)} Microsoft prerequisite(s) are missing.", 18)
                self.after(0, lambda: self.update_button.config(state="normal", text="INSTALL REQUIREMENTS"))
            else:
                self.prerequisites_only = False
                self.ui("ATLAS is up to date", f"Version {local} is ready to launch.", 100)
            if installed:
                self.after(0, lambda: self.launch_button.config(state="normal"))
        except Exception as exc:
            installed = (INSTALL_DIR / APP_EXE).exists()
            self.ui("Update check unavailable", f"{exc}\nYou can still launch the installed version.", 0)
            if installed:
                self.after(0, lambda: self.launch_button.config(state="normal"))

    def _asset_url(self, name: str) -> str:
        if not self.remote_release:
            raise RuntimeError("No release information is loaded")
        for asset in self.remote_release.get("assets", []):
            if asset.get("name") == name:
                return str(asset["browser_download_url"])
        raise RuntimeError(f"Release asset is missing: {name}")

    def _download(self, url: str, destination: Path, start: float, span: float) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": "ATLAS-Launcher/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length", 0))
            received = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output.write(chunk)
                received += len(chunk)
                percent = (received / total) if total else 0
                self.ui("Downloading ATLAS...", f"{received / 1_048_576:.1f} MB received", start + span * percent)

    def install_update(self) -> None:
        if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
            messagebox.showerror("ATLAS Launcher", "ATLAS currently requires 64-bit Windows 10 or Windows 11.")
            return
        self.prerequisites_to_install = missing_prerequisites()
        if self.prerequisites_to_install:
            labels = "\n".join(f"- {PREREQUISITES[key]['label']}" for key in self.prerequisites_to_install)
            approved = messagebox.askyesno(
                "ATLAS Prerequisites",
                "ATLAS needs the following Microsoft components:\n\n"
                f"{labels}\n\nInstall them automatically with Windows Package Manager?",
            )
            if not approved:
                self.ui("Installation paused", "Install the listed Microsoft prerequisites, then try again.", 0)
                return
        self.update_button.config(state="disabled")
        self.launch_button.config(state="disabled")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        backup = INSTALL_DIR.with_name(f"{APP_FOLDER}.backup")
        try:
            self._install_prerequisites(self.prerequisites_to_install)
            if self.prerequisites_only:
                self._create_shortcuts()
                self.ui("Requirements installed", "ATLAS is ready to launch.", 100)
                self.after(0, lambda: self.launch_button.config(state="normal"))
                self.after(0, lambda: self.update_button.config(state="disabled"))
                return
            with tempfile.TemporaryDirectory(prefix="atlas-update-") as temp_name:
                temp = Path(temp_name)
                archive = temp / ZIP_ASSET
                manifest_path = temp / MANIFEST_ASSET
                self._download(self._asset_url(MANIFEST_ASSET), manifest_path, 5, 5)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self._download(self._asset_url(ZIP_ASSET), archive, 10, 55)
                actual_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
                expected_hash = str(manifest.get("sha256", "")).lower()
                if not expected_hash or actual_hash.lower() != expected_hash:
                    raise RuntimeError("The downloaded update failed its security check")

                self.ui("Preparing update...", "Verifying application files.", 72)
                staging = temp / "staging"
                with zipfile.ZipFile(archive) as package:
                    for member in package.infolist():
                        target = (staging / member.filename).resolve()
                        if staging.resolve() not in target.parents and target != staging.resolve():
                            raise RuntimeError("Update package contains an unsafe path")
                    package.extractall(staging)
                if not (staging / APP_EXE).exists():
                    raise RuntimeError("The update package does not contain ATLAS")

                self.ui("Installing update...", "Keeping a rollback copy of the previous version.", 84)
                if backup.exists():
                    shutil.rmtree(backup)
                if INSTALL_DIR.exists():
                    INSTALL_DIR.replace(backup)
                try:
                    shutil.move(str(staging), str(INSTALL_DIR))
                except Exception:
                    if INSTALL_DIR.exists():
                        shutil.rmtree(INSTALL_DIR, ignore_errors=True)
                    if backup.exists():
                        backup.replace(INSTALL_DIR)
                    raise
                if backup.exists():
                    shutil.rmtree(backup, ignore_errors=True)

            self._create_shortcuts()

            self.ui("Update complete", "ATLAS is installed and ready.", 100)
            self.after(0, lambda: self.launch_button.config(state="normal"))
            self.after(0, lambda: self.update_button.config(state="disabled"))
        except Exception as exc:
            self.ui("Update failed", str(exc), 0)
            self.after(0, lambda: self.update_button.config(state="normal"))
            if (INSTALL_DIR / APP_EXE).exists():
                self.after(0, lambda: self.launch_button.config(state="normal"))
            self.after(0, lambda: messagebox.showerror("ATLAS Update", f"The update could not be installed.\n\n{exc}"))

    def _install_prerequisites(self, prerequisite_keys: list[str]) -> None:
        if not prerequisite_keys:
            return
        winget = shutil.which("winget.exe") or shutil.which("winget")
        if not winget:
            raise RuntimeError("Windows Package Manager is unavailable. Install 'App Installer' from the Microsoft Store, then try again.")
        for index, key in enumerate(prerequisite_keys, start=1):
            definition = PREREQUISITES[key]
            self.ui(
                "Installing prerequisites...",
                f"{index}/{len(prerequisite_keys)}: {definition['label']}",
                2 + (index - 1) * 3,
            )
            command = [
                str(winget), "install", "--id", str(definition["winget_id"]), "--exact",
                "--silent", "--accept-package-agreements", "--accept-source-agreements",
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=600, shell=False)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "Unknown installer error").strip()[-600:]
                raise RuntimeError(f"Could not install {definition['label']}: {detail}")

    def _create_shortcuts(self) -> None:
        launcher_path = Path(sys.executable).resolve()
        if not getattr(sys, "frozen", False) or not launcher_path.exists():
            return
        try:
            import win32com.client
        except ImportError:
            return
        shortcut_target = launcher_path
        if INSTALL_DIR == MANAGED_INSTALL_DIR:
            MANAGED_LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
            installed_launcher = MANAGED_LAUNCHER_DIR / "JARVIS Launcher.exe"
            if launcher_path != installed_launcher:
                shutil.copy2(launcher_path, installed_launcher)
            shortcut_target = installed_launcher
        shortcut_locations = [
            Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "ATLAS Launcher.lnk",
            Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "ATLAS Launcher.lnk",
        ]
        shell = win32com.client.Dispatch("WScript.Shell")
        for shortcut_path in shortcut_locations:
            shortcut_path.parent.mkdir(parents=True, exist_ok=True)
            shortcut = shell.CreateShortcut(str(shortcut_path))
            shortcut.TargetPath = str(shortcut_target)
            shortcut.WorkingDirectory = str(shortcut_target.parent)
            shortcut.IconLocation = f"{shortcut_target},0"
            shortcut.Description = "Launch and update ATLAS"
            shortcut.Save()

    def launch(self) -> None:
        executable = INSTALL_DIR / APP_EXE
        if not executable.exists():
            messagebox.showerror("ATLAS Launcher", "ATLAS is not installed yet.")
            return
        subprocess.Popen([str(executable)], cwd=str(INSTALL_DIR), close_fds=True)
        self.after(300, self.destroy)


if __name__ == "__main__":
    JarvisLauncher().mainloop()
