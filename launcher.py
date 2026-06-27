"""JARVIS Launcher: installs, verifies, updates, rolls back, and launches JARVIS."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


REPOSITORY = "JMick27/J.A.R.V.I.S"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
APP_FOLDER = "JARVIS Desktop Assistant"
APP_EXE = "JARVIS Desktop Assistant.exe"
ZIP_ASSET = "JARVIS-win-x64.zip"
MANIFEST_ASSET = "release-manifest.json"
INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_FOLDER
LOCAL_VERSION_FILE = INSTALL_DIR / "version.json"


def version_tuple(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lower().lstrip("v")
    return tuple(int(part) for part in cleaned.split(".") if part.isdigit()) or (0,)


class JarvisLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JARVIS Launcher")
        self.geometry("640x410")
        self.minsize(540, 360)
        self.configure(bg="#030712")
        self.remote_release: dict | None = None
        self._build_ui()
        self.after(250, self.check_for_updates)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Jarvis.Horizontal.TProgressbar", troughcolor="#07111f", background="#38bdf8")

        tk.Label(self, text="J.A.R.V.I.S.", bg="#030712", fg="#76e4ff", font=("Segoe UI", 32, "bold")).pack(pady=(36, 2))
        tk.Label(self, text="DESKTOP SYSTEM LAUNCHER", bg="#030712", fg="#8fb7c8", font=("Segoe UI", 10)).pack()
        self.status = tk.Label(self, text="Checking systems...", bg="#030712", fg="#e6fbff", font=("Segoe UI", 13))
        self.status.pack(pady=(36, 12))
        self.progress = ttk.Progressbar(self, style="Jarvis.Horizontal.TProgressbar", mode="determinate", maximum=100, length=460)
        self.progress.pack()
        self.detail = tk.Label(self, text="", bg="#030712", fg="#8fb7c8", wraplength=520, justify="center", font=("Segoe UI", 9))
        self.detail.pack(pady=12)

        buttons = tk.Frame(self, bg="#030712")
        buttons.pack(side="bottom", pady=32)
        self.launch_button = tk.Button(buttons, text="LAUNCH JARVIS", command=self.launch, state="disabled", bg="#0d2236", fg="#e6fbff", activebackground="#12384f", activeforeground="#ffffff", relief="flat", padx=26, pady=10)
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
        self.ui("Checking for updates...", "Contacting the JARVIS release channel.", 8)
        try:
            request = urllib.request.Request(RELEASE_API, headers={"User-Agent": "JARVIS-Launcher/0.1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                release = json.load(response)
            self.remote_release = release
            remote = str(release.get("tag_name", "0.0.0")).lstrip("v")
            local = self.local_version()
            installed = (INSTALL_DIR / APP_EXE).exists()
            if not installed or version_tuple(remote) > version_tuple(local):
                label = "Installation ready" if not installed else "Update available"
                self.ui(label, f"Version {remote} is ready. Installed version: {local}.", 18)
                self.after(0, lambda: self.update_button.config(state="normal", text="INSTALL" if not installed else "INSTALL UPDATE"))
            else:
                self.ui("JARVIS is up to date", f"Version {local} is ready to launch.", 100)
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
        request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Launcher/0.1"})
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
                self.ui("Downloading JARVIS...", f"{received / 1_048_576:.1f} MB received", start + span * percent)

    def install_update(self) -> None:
        self.update_button.config(state="disabled")
        self.launch_button.config(state="disabled")
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self) -> None:
        backup = INSTALL_DIR.with_name(f"{APP_FOLDER}.backup")
        try:
            with tempfile.TemporaryDirectory(prefix="jarvis-update-") as temp_name:
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
                    raise RuntimeError("The update package does not contain JARVIS")

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

            self.ui("Update complete", "JARVIS is installed and ready.", 100)
            self.after(0, lambda: self.launch_button.config(state="normal"))
            self.after(0, lambda: self.update_button.config(state="disabled"))
        except Exception as exc:
            self.ui("Update failed", str(exc), 0)
            self.after(0, lambda: self.update_button.config(state="normal"))
            if (INSTALL_DIR / APP_EXE).exists():
                self.after(0, lambda: self.launch_button.config(state="normal"))
            self.after(0, lambda: messagebox.showerror("JARVIS Update", f"The update could not be installed.\n\n{exc}"))

    def launch(self) -> None:
        executable = INSTALL_DIR / APP_EXE
        if not executable.exists():
            messagebox.showerror("JARVIS Launcher", "JARVIS is not installed yet.")
            return
        subprocess.Popen([str(executable)], cwd=str(INSTALL_DIR), close_fds=True)
        self.after(300, self.destroy)


if __name__ == "__main__":
    JarvisLauncher().mainloop()
