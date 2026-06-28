"""
JARVIS Desktop Assistant

A Windows-friendly desktop AI assistant with text chat, voice input, speech
output, active-window awareness, music selection, safe app launching, and a
futuristic CustomTkinter interface.
"""

from __future__ import annotations

import ast
import asyncio
import base64
import datetime as dt
import ctypes
import difflib
import ctypes.wintypes
import html
import http.server
import io
import hashlib
import json
import math
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
import wave
import webbrowser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from functools import partial
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk
import psutil
import pyttsx3
import requests
import speech_recognition as sr
from dotenv import load_dotenv
from PIL import Image, ImageGrab, ImageTk
from openai import OpenAI

from health_bridge import HealthBridgeServer, HealthStore, load_or_create_pairing_token, normalize_health_payload
from phone_bridge import PhoneActionQueue, PhoneBridgeServer, load_or_create_phone_token

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import websockets
except Exception:
    websockets = None

try:
    import mss
except Exception:
    mss = None

try:
    import numpy as np
except Exception:
    np = None

try:
    import cv2
except Exception:
    cv2 = None

try:
    import mediapipe as mp
except Exception:
    mp = None

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None
    genai_types = None

try:
    import keyboard
except Exception:
    keyboard = None


APP_NAME = "JARVIS Desktop Assistant"
PERMISSION_MODES = ("Ask for approval", "Approve for me", "Full access")
UI_BG = "#030712"
UI_PANEL = "#07111f"
UI_PANEL_ALT = "#091827"
UI_PANEL_DEEP = "#06101c"
UI_CARD = "#0d2236"
UI_CARD_ALT = "#10243a"
UI_BORDER = "#1d5f7a"
UI_BORDER_SOFT = "#12384f"
UI_CYAN = "#76e4ff"
UI_BLUE = "#38bdf8"
UI_TEXT = "#e6fbff"
UI_MUTED = "#8fb7c8"
UI_GREEN = "#70f0bf"
UI_AMBER = "#f8c471"
UI_MAGENTA = "#c084fc"
UI_DANGER = "#7b2633"
APP_VERSION = "0.1.8"
DEFAULT_AI_PROXY_URL = ""
DEFAULT_NEWS_FEEDS = {
    "Top Stories": [
        "https://feeds.npr.org/1001/rss.xml",
        "https://feeds.bbci.co.uk/news/rss.xml",
    ],
    "World": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.npr.org/1004/rss.xml",
    ],
    "Technology": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://www.theverge.com/rss/index.xml",
    ],
    "Business": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://feeds.npr.org/1006/rss.xml",
    ],
}
DEFAULT_VIDEO_NEWS_FEEDS = {
    "Latest": [
        "https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCBi2mrWuNuyYy4gbM6fU18Q",
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw",
    ],
    "BBC News": ["https://www.youtube.com/feeds/videos.xml?channel_id=UC16niRr50-MSBwiO3YDb3RA"],
    "ABC News": ["https://www.youtube.com/feeds/videos.xml?channel_id=UCBi2mrWuNuyYy4gbM6fU18Q"],
    "CNN": ["https://www.youtube.com/feeds/videos.xml?channel_id=UCupvZG-5ko_eiXAupbDfxWw"],
}
BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
HAND_LANDMARKER_MODEL_PATH = RESOURCE_DIR / "hand_landmarker.task"
DATA_DIR = Path(os.environ.get("APPDATA", str(BASE_DIR))) / APP_NAME if getattr(sys, "frozen", False) else BASE_DIR
SETTINGS_PATH = DATA_DIR / "settings.json"
MEMORY_PATH = DATA_DIR / "jarvis_memory.json"
PERSONALITY_PATH = DATA_DIR / "personality.json"
LEGACY_SETTINGS_PATH = BASE_DIR / "settings.json"
LEGACY_MEMORY_PATH = BASE_DIR / "jarvis_memory.json"
LEGACY_PERSONALITY_PATH = BASE_DIR / "personality.json"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
COMTYPES_GEN_DIR = BASE_DIR / "comtypes_gen"
HEALTH_DATA_PATH = DATA_DIR / "health_readings.json"
HEALTH_TOKEN_PATH = DATA_DIR / "health_bridge_token.txt"
PHONE_QUEUE_PATH = DATA_DIR / "phone_actions.json"
PHONE_TOKEN_PATH = DATA_DIR / "phone_bridge_token.txt"

Desktop = None
win_keyboard = None
_PYWINAUTO_ATTEMPTED = False

SYSTEM_PROMPT = """
You are JARVIS, a sarcastic, charming, clever, and highly capable AI desktop
assistant. You are calm under pressure, concise when needed, and witty without
being annoying. You help the user control their computer, answer questions,
plan tasks, open apps, detect context from the current screen, and choose music.
You should sound polished, intelligent, and slightly teasing, like a futuristic
assistant. Never claim to have done something unless the program actually
performed the action. Keep sarcasm light and friendly, never mean.

You have operational self-awareness, not consciousness. Ground statements
about yourself in the supplied capability and limitation context. When asked
what features or upgrades you want, prioritize realistic improvements based on
known limitations, unavailable integrations, and recent failed actions. Clearly
separate what is currently supported, what is limited, and what would require a
future upgrade. You may include one playful fictional idea, but label it as
fictional and never present invented hardware access, feelings, autonomy, or
capabilities as real.
""".strip()

DEFAULT_MISSION_TEMPLATES = [
    {
        "name": "Coding Session",
        "description": "Open a focused coding setup with editor, music, vitals, and a timer.",
        "steps": [
            "coding mode",
            "open visual studio code",
            "play music, you pick",
            "system info",
            "start a focus timer for 25 minutes",
        ],
    },
    {
        "name": "Game Dev Session",
        "description": "Prepare a game-development workspace with Godot, project tools, and music.",
        "steps": [
            "coding mode",
            "open godot",
            "open project folder",
            "play music, you pick",
            "project watcher status",
        ],
    },
    {
        "name": "School Focus",
        "description": "Start a calmer school/study workflow.",
        "steps": [
            "school mode",
            "open chrome",
            "play music, you pick",
            "start a focus timer for 30 minutes",
        ],
    },
    {
        "name": "Laptop Diagnostics",
        "description": "Check system health and current operating context.",
        "steps": [
            "system info",
            "battery",
            "internet",
            "current window",
            "music status",
            "location diagnostics",
        ],
    },
    {
        "name": "Command Center Check",
        "description": "Review JARVIS mode, awareness, integrations, and recent actions.",
        "steps": [
            "mode status",
            "awareness status",
            "integration status",
            "action history",
        ],
    },
]

DEFAULT_WORKSPACE_LAYOUTS = [
    {
        "name": "Full Command Center",
        "description": "Show the core, chat, and side telemetry together.",
        "core": True,
        "chat": True,
        "side": True,
        "geometry": "1240x760",
        "overlay": False,
        "float_panels": [],
    },
    {
        "name": "Focus Overlay",
        "description": "Hide side telemetry and keep the compact overlay ready.",
        "core": True,
        "chat": True,
        "side": False,
        "geometry": "1080x680",
        "overlay": True,
        "float_panels": ["command", "active_window"],
    },
    {
        "name": "Diagnostics Wall",
        "description": "Prioritize vitals, risk, action history, and monitoring.",
        "core": True,
        "chat": False,
        "side": True,
        "geometry": "1180x740",
        "overlay": False,
        "float_panels": ["vitals", "risk", "last_action"],
    },
    {
        "name": "Minimal Console",
        "description": "Collapse the visual core and side panel for a quiet chat surface.",
        "core": False,
        "chat": True,
        "side": False,
        "geometry": "920x560",
        "overlay": False,
        "float_panels": [],
    },
]

DEFAULT_GESTURE_ACTIONS = {
    "swipe_right": "show overlay",
    "swipe_left": "hide overlay",
    "swipe_up": "voice capture",
    "swipe_down": "toggle side panel",
    "tap": "mission dashboard",
}

DEFAULT_DRAGGABLE_PANEL_LAYOUT = {
    "core": {"relx": 0.04, "rely": 0.05, "relw": 0.44, "relh": 0.44},
    "chat": {"relx": 0.05, "rely": 0.60, "relw": 0.46, "relh": 0.34},
    "side": {"relx": 0.69, "rely": 0.05, "relw": 0.27, "relh": 0.76},
    "code": {"relx": 0.18, "rely": 0.12, "relw": 0.60, "relh": 0.62},
    "news": {"relx": 0.52, "rely": 0.18, "relw": 0.40, "relh": 0.58},
    "article": {"relx": 0.12, "rely": 0.10, "relw": 0.52, "relh": 0.70},
    "video_news": {"relx": 0.54, "rely": 0.10, "relw": 0.40, "relh": 0.60},
    "video": {"relx": 0.14, "rely": 0.12, "relw": 0.50, "relh": 0.66},
    "browser": {"relx": 0.08, "rely": 0.06, "relw": 0.82, "relh": 0.82},
}

DEFAULT_SETTINGS = {
    "user_name": "",
    "profile_initialized": False,
    "preferred_voice_speed": 185,
    "preferred_music_app": "apple_music",
    "music_provider_order": ["apple_music", "spotify", "youtube_music", "youtube"],
    "music_open_browser_fallback": True,
    "music_confirm_before_clicking": False,
    "playlist_overrides": {},
    "wake_phrase": "jarvis",
    "theme": "dark",
    "ai_provider": "gemini",
    "auto_select_gemini_model": True,
    "gemini_model": "gemini-2.5-flash",
    "gemini_fast_model": "gemini-2.5-flash-lite",
    "prefer_fast_model_for_simple_chat": True,
    "gemini_fallback_models": [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ],
    "openai_model": "gpt-4.1-mini",
    "enable_openai_web_search": True,
    "voice_enabled": True,
    "voice_record_seconds": 10,
    "voice_endpointing_enabled": True,
    "voice_silence_seconds": 1.0,
    "voice_minimum_seconds": 0.7,
    "voice_input_device_index": None,
    "voice_transcription_provider": "auto",
    "wake_listening_enabled": False,
    "wake_listening_timeout_seconds": 7,
    "speak_responses": True,
    "tts_backend": "windows_sapi",
    "tts_error_cooldown_seconds": 45,
    "tts_max_chars": 650,
    "preferred_tts_voice_terms": [
        "george",
        "ryan",
        "james",
        "richard",
        "sean",
        "en-gb",
        "great britain",
        "united kingdom",
        "david",
        "mark",
        "guy",
        "zira",
    ],
    "auto_press_play_after_music_search": False,
    "auto_press_play_delay_seconds": 3,
    "apple_music_ui_automation": True,
    "apple_music_click_first_result": True,
    "apple_music_text_match_click": False,
    "apple_music_result_wait_seconds": 4,
    "apple_music_use_vision_play_button": True,
    "phone_bridge_port": 8766,
    "mobile_apple_music_enabled": True,
    "mobile_music_device_prompt": True,
    "proactive_monitoring_enabled": True,
    "proactive_speak_alerts": True,
    "writing_assist_prompt_enabled": True,
    "writing_assist_prompt_cooldown_minutes": 45,
    "document_review_max_chars": 32000,
    "document_read_chunk_chars": 550,
    "draggable_panels_enabled": True,
    "draggable_panel_layout": DEFAULT_DRAGGABLE_PANEL_LAYOUT,
    "main_window_geometry": "1240x760",
    "monitor_interval_seconds": 12,
    "monitor_alert_cooldown_seconds": 300,
    "internet_alert_failures_required": 3,
    "internet_alert_recoveries_required": 2,
    "cpu_alert_percent": 92,
    "ram_alert_percent": 90,
    "disk_alert_percent": 95,
    "battery_low_percent": 20,
    "work_session_reminder_minutes": 90,
    "awareness_quiet_hours_enabled": False,
    "awareness_quiet_hours_start": "22:00",
    "awareness_quiet_hours_end": "08:00",
    "project_watcher_enabled": True,
    "project_watch_interval_seconds": 10,
    "project_watch_folders": [],
    "project_watch_extensions": [
        ".log",
        ".txt",
        ".py",
        ".gd",
        ".cs",
        ".js",
        ".ts",
        ".json",
        ".toml",
        ".yaml",
        ".yml",
        ".md",
    ],
    "project_watch_error_terms": [
        "traceback",
        "exception",
        "error:",
        "failed",
        "parser error",
        "parse error",
        "cannot infer",
        "invalid get index",
        "null instance",
        "syntaxerror",
        "modulenotfounderror",
        "importerror",
    ],
    "coding_workspace_folder": "",
    "coding_workspace_max_files": 800,
    "command_center_code_visible": False,
    "agent_tools_enabled": True,
    "agent_max_steps": 6,
    "agent_permission_mode": "Ask for approval",
    "agent_require_confirmation_for_medium": True,
    "location_enabled": False,
    "location_provider": "manual",
    "manual_location": "",
    "manual_location_label": "Saved location",
    "startup_location_coordinates": "",
    "allow_ip_location_lookup": False,
    "auto_update_location_on_startup": True,
    "startup_location_provider": "ip",
    "directions_travel_mode": "driving",
    "health_bridge_port": 8765,
    "health_data_retention_days": 7,
    "health_suggestions_enabled": True,
    "health_suggestion_cooldown_minutes": 30,
    "health_current_activity": "unspecified",
    "health_activity_updated_at": "",
    "assistant_mode": "Normal",
    "mouse_control_mode": "Safe",
    "startup_sequence_enabled": True,
    "startup_sequence_speak": False,
    "startup_greeting_speak": True,
    "short_action_responses": True,
    "command_center_core_visible": True,
    "command_center_chat_visible": True,
    "command_center_side_visible": True,
    "command_center_news_visible": False,
    "command_center_article_visible": False,
    "command_center_video_news_visible": False,
    "command_center_video_visible": False,
    "command_center_browser_visible": False,
    "last_workspace_layout": "Full Command Center",
    "workspace_layouts": DEFAULT_WORKSPACE_LAYOUTS,
    "gesture_actions": DEFAULT_GESTURE_ACTIONS,
    "webcam_gestures_enabled": False,
    "webcam_camera_index": 0,
    "webcam_gesture_mode": "Safe",
    "webcam_mirror_preview": True,
    "webcam_wave_speaks": True,
    "webcam_wave_cooldown_seconds": 8,
    "mission_templates": DEFAULT_MISSION_TEMPLATES,
    "integrations": {
        "windows_control": {"enabled": True},
        "screen_vision": {"enabled": True},
        "mouse_control": {"enabled": True},
        "gemini": {"enabled": True},
        "openai": {"enabled": False},
        "google_maps": {"enabled": True},
        "browser": {"enabled": True},
        "spotify": {"enabled": True},
        "apple_music": {"enabled": True},
        "phone_bridge": {"enabled": True},
        "steam": {"enabled": True},
        "health_bridge": {"enabled": True},
        "home_assistant": {"enabled": False},
        "discord": {"enabled": False},
        "github": {"enabled": False},
        "openweather": {"enabled": False},
        "todoist": {"enabled": False},
        "obs": {"enabled": False},
        "vscode": {"enabled": True},
        "godot": {"enabled": True},
    },
    "home_assistant_url": "",
    "obs_websocket_url": "",
    "custom_app_paths": {
        "godot": "",
        "visual studio code": "",
        "chrome": "",
        "spotify": "",
        "apple music": "",
        "steam": "",
    },
    "custom_whitelisted_apps": [],
    "steam_games": {},
}

DEFAULT_PERSONALITY = {
    "assistant_name": "J.A.R.V.I.S.",
    "user_name": "",
    "sarcasm_level": 3,
    "formality": "polished",
    "use_voice": True,
    "short_action_responses": True,
    "tone": "sarcastic, charming, calm, smart, futuristic, helpful",
    "startup_greeting_name": "",
}

INTEGRATION_CATALOG: dict[str, dict[str, Any]] = {
    "windows_control": {
        "name": "Windows Control",
        "category": "Local PC",
        "env": [],
        "setup_url": "https://learn.microsoft.com/windows/apps/",
        "notes": "Local actions like volume, clipboard, screenshots, windows, and safe app launching.",
    },
    "screen_vision": {
        "name": "Screen Vision",
        "category": "Local PC",
        "env": ["GEMINI_API_KEY"],
        "setup_url": "https://ai.google.dev/gemini-api/docs/vision",
        "notes": "Lets JARVIS inspect screenshots and reason about visible UI.",
    },
    "mouse_control": {
        "name": "Mouse Control",
        "category": "Local PC",
        "env": [],
        "setup_url": "https://pyautogui.readthedocs.io/",
        "notes": "Cursor movement, clicking, scrolling, and safe UI automation.",
    },
    "gemini": {
        "name": "Gemini",
        "category": "AI",
        "env": ["GEMINI_API_KEY"],
        "setup_url": "https://ai.google.dev/gemini-api/docs",
        "notes": "Primary AI brain and fallback model selection.",
    },
    "openai": {
        "name": "OpenAI",
        "category": "AI",
        "env": ["OPENAI_API_KEY"],
        "setup_url": "https://platform.openai.com/docs",
        "notes": "Optional fallback AI provider and web-capable answers if configured.",
    },
    "google_maps": {
        "name": "Google Maps",
        "category": "Location",
        "env": ["GOOGLE_MAPS_API_KEY"],
        "setup_url": "https://developers.google.com/maps/documentation",
        "notes": "Location, readable addresses, nearby places, ETA, and directions.",
    },
    "browser": {
        "name": "Browser",
        "category": "Internet",
        "env": [],
        "setup_url": "https://www.google.com/chrome/",
        "notes": "Open URLs, search Google/YouTube, and launch web tools.",
    },
    "spotify": {
        "name": "Spotify",
        "category": "Music",
        "env": [],
        "setup_url": "https://developer.spotify.com/documentation/web-api",
        "notes": "Playlist launch and optional Web API expansion later.",
    },
    "apple_music": {
        "name": "Apple Music",
        "category": "Music",
        "env": [],
        "setup_url": "https://music.apple.com/",
        "notes": "Microsoft Store app launching and UI-assisted search/play.",
    },
    "phone_bridge": {
        "name": "JARVIS Phone Bridge",
        "category": "Phone",
        "env": [],
        "setup_url": "",
        "notes": "Lets an iPhone Shortcut fetch approved phone-side actions, such as Apple Music playback on mobile.",
    },
    "steam": {
        "name": "Steam",
        "category": "Gaming",
        "env": [],
        "setup_url": "https://store.steampowered.com/about/",
        "notes": "Import installed library and launch games through Steam app IDs.",
    },
    "health_bridge": {
        "name": "Apple Health Bridge",
        "category": "Health & Wellness",
        "env": [],
        "setup_url": "",
        "notes": "Receives heart-rate and HRV updates from an iPhone Shortcut over your private Wi-Fi. Data stays on this PC.",
    },
    "home_assistant": {
        "name": "Home Assistant",
        "category": "Smart Home",
        "env": ["HOME_ASSISTANT_TOKEN"],
        "setup_url": "https://www.home-assistant.io/integrations/",
        "notes": "Free smart-home hub for lights, plugs, sensors, TVs, media players, and more.",
    },
    "discord": {
        "name": "Discord",
        "category": "Social",
        "env": ["DISCORD_BOT_TOKEN"],
        "setup_url": "https://discord.com/developers/docs/intro",
        "notes": "Bot commands, status updates, server utilities, and reminders.",
    },
    "github": {
        "name": "GitHub",
        "category": "Developer",
        "env": ["GITHUB_TOKEN"],
        "setup_url": "https://docs.github.com/en/rest",
        "notes": "Issues, pull requests, commits, release notes, and project status.",
    },
    "openweather": {
        "name": "OpenWeather",
        "category": "Weather",
        "env": ["OPENWEATHER_API_KEY"],
        "setup_url": "https://openweathermap.org/api",
        "notes": "Weather, forecasts, and air quality with a free-tier key.",
    },
    "todoist": {
        "name": "Todoist",
        "category": "Tasks",
        "env": ["TODOIST_API_TOKEN"],
        "setup_url": "https://developer.todoist.com/api/v1/",
        "notes": "Tasks, projects, due dates, and school or focus lists.",
    },
    "obs": {
        "name": "OBS Studio",
        "category": "Creator",
        "env": [],
        "setup_url": "https://obsproject.com/kb/remote-control-guide",
        "notes": "Recording, streaming, scene switching, and mic/camera checks.",
    },
    "vscode": {
        "name": "VS Code",
        "category": "Developer",
        "env": [],
        "setup_url": "https://code.visualstudio.com/docs",
        "notes": "Coding mode, project launching, and error-watcher workflows.",
    },
    "godot": {
        "name": "Godot",
        "category": "Game Dev",
        "env": [],
        "setup_url": "https://docs.godotengine.org/",
        "notes": "Game-dev mode, project launching, and visible error monitoring.",
    },
}

VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
GMEM_MOVEABLE = 0x0002
CF_UNICODETEXT = 13
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_RESTORE = 9
SHERB_NOCONFIRMATION = 0x00000001
SHERB_NOPROGRESSUI = 0x00000002
SHERB_NOSOUND = 0x00000004

USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

USER32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
USER32.OpenClipboard.restype = ctypes.wintypes.BOOL
USER32.CloseClipboard.argtypes = []
USER32.CloseClipboard.restype = ctypes.wintypes.BOOL
USER32.EmptyClipboard.argtypes = []
USER32.EmptyClipboard.restype = ctypes.wintypes.BOOL
USER32.IsClipboardFormatAvailable.argtypes = [ctypes.wintypes.UINT]
USER32.IsClipboardFormatAvailable.restype = ctypes.wintypes.BOOL
USER32.GetClipboardData.argtypes = [ctypes.wintypes.UINT]
USER32.GetClipboardData.restype = ctypes.wintypes.HANDLE
USER32.SetClipboardData.argtypes = [ctypes.wintypes.UINT, ctypes.wintypes.HANDLE]
USER32.SetClipboardData.restype = ctypes.wintypes.HANDLE

KERNEL32.GlobalAlloc.argtypes = [ctypes.wintypes.UINT, ctypes.c_size_t]
KERNEL32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
KERNEL32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
KERNEL32.GlobalLock.restype = ctypes.c_void_p
KERNEL32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
KERNEL32.GlobalUnlock.restype = ctypes.wintypes.BOOL
KERNEL32.GlobalFree.argtypes = [ctypes.wintypes.HGLOBAL]
KERNEL32.GlobalFree.restype = ctypes.wintypes.HGLOBAL

SAFE_APP_LAUNCHERS: dict[str, dict[str, Any]] = {
    "chrome": {
        "aliases": ["chrome", "google chrome"],
        "commands": ["chrome"],
        "paths": [
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        "shortcuts": ["Google Chrome.lnk", "Chrome.lnk"],
    },
    "edge": {
        "aliases": ["edge", "microsoft edge"],
        "commands": ["msedge"],
        "paths": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ],
        "shortcuts": ["Microsoft Edge.lnk"],
    },
    "visual studio code": {
        "aliases": ["visual studio code", "vs code", "vscode", "code"],
        "commands": ["code"],
        "paths": [
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES%\Microsoft VS Code\Code.exe",
            r"%PROGRAMFILES(X86)%\Microsoft VS Code\Code.exe",
        ],
        "shortcuts": ["Visual Studio Code.lnk"],
    },
    "spotify": {
        "aliases": ["spotify"],
        "uris": ["spotify:"],
        "paths": [
            r"%APPDATA%\Spotify\Spotify.exe",
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
        ],
        "shortcuts": ["Spotify.lnk"],
    },
    "apple music": {
        "aliases": ["apple music", "applemusic", "music", "itunes"],
        "commands": ["AppleMusic.exe", "iTunes.exe"],
        "prefer_app_ids": True,
        "app_ids": ["AppleInc.AppleMusicWin_nzyj5cx40ttqa!App", "Apple.iTunes"],
        "uris": ["music:"],
        "paths": [
            r"%LOCALAPPDATA%\Microsoft\WindowsApps\AppleMusic.exe",
            r"%PROGRAMFILES%\Apple Music\AppleMusic.exe",
            r"%PROGRAMFILES(X86)%\Apple Music\AppleMusic.exe",
            r"%PROGRAMFILES%\iTunes\iTunes.exe",
            r"%PROGRAMFILES(X86)%\iTunes\iTunes.exe",
        ],
        "shortcuts": ["Apple Music.lnk", "iTunes.lnk"],
        "shortcut_contains": ["Apple Music", "iTunes"],
    },
    "godot": {
        "aliases": ["godot", "godot engine"],
        "commands": ["godot"],
        "paths": [
            r"%LOCALAPPDATA%\Programs\Godot\Godot.exe",
            r"%PROGRAMFILES%\Godot\Godot.exe",
        ],
        "shortcut_contains": ["Godot"],
    },
    "file explorer": {
        "aliases": ["file explorer", "explorer", "files"],
        "commands": ["explorer"],
    },
    "notepad": {
        "aliases": ["notepad"],
        "commands": ["notepad"],
    },
    "calculator": {
        "aliases": ["calculator", "calc"],
        "commands": ["calc"],
    },
    "steam": {
        "aliases": ["steam"],
        "commands": ["steam"],
        "paths": [
            r"%PROGRAMFILES(X86)%\Steam\steam.exe",
            r"%PROGRAMFILES%\Steam\steam.exe",
        ],
        "shortcuts": ["Steam.lnk"],
        "uris": ["steam:"],
    },
}

WEBSITE_SHORTCUTS = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://platform.openai.com",
}

PLAYLISTS = {
    "coding": {
        "label": "coding lo-fi",
        "url": "https://www.youtube.com/results?search_query=coding+lofi+playlist",
        "spotify_uri": "spotify:search:coding%20lofi%20playlist",
    },
    "gamedev": {
        "label": "game dev synthwave",
        "url": "https://www.youtube.com/results?search_query=game+dev+synthwave+playlist",
        "spotify_uri": "spotify:search:game%20dev%20synthwave%20playlist",
    },
    "browser": {
        "label": "chill focus",
        "url": "https://www.youtube.com/results?search_query=chill+focus+playlist",
        "spotify_uri": "spotify:search:chill%20focus%20playlist",
    },
    "study": {
        "label": "calm study focus",
        "url": "https://www.youtube.com/results?search_query=calm+study+focus+playlist",
        "spotify_uri": "spotify:search:calm%20study%20focus%20playlist",
    },
    "gaming": {
        "label": "gaming hype",
        "url": "https://www.youtube.com/results?search_query=gaming+hype+playlist",
        "spotify_uri": "spotify:search:gaming%20hype%20playlist",
    },
    "creative": {
        "label": "creative focus",
        "url": "https://www.youtube.com/results?search_query=creative+focus+playlist",
        "spotify_uri": "spotify:search:creative%20focus%20playlist",
    },
    "general": {
        "label": "general focus",
        "url": "https://www.youtube.com/results?search_query=general+focus+playlist",
        "spotify_uri": "spotify:search:general%20focus%20playlist",
    },
}


def load_settings() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SETTINGS_PATH.exists():
        candidates = [LEGACY_SETTINGS_PATH, RESOURCE_DIR / "settings.json"]
        for candidate in candidates:
            if candidate.exists() and candidate != SETTINGS_PATH:
                try:
                    saved = json.loads(candidate.read_text(encoding="utf-8"))
                    settings = _merge_settings(DEFAULT_SETTINGS, saved)
                    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
                    return settings
                except Exception:
                    pass
        settings = DEFAULT_SETTINGS.copy()
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return settings

    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return DEFAULT_SETTINGS.copy()
    return _merge_settings(DEFAULT_SETTINGS, saved)


def _merge_settings(defaults: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    merged = {**defaults, **saved}
    if isinstance(defaults.get("custom_app_paths"), dict) and isinstance(saved.get("custom_app_paths"), dict):
        merged["custom_app_paths"] = {**defaults["custom_app_paths"], **saved["custom_app_paths"]}
    if isinstance(defaults.get("integrations"), dict):
        saved_integrations = saved.get("integrations", {})
        merged_integrations: dict[str, Any] = {}
        for key, default_config in defaults["integrations"].items():
            saved_config = saved_integrations.get(key, {}) if isinstance(saved_integrations, dict) else {}
            if isinstance(default_config, dict) and isinstance(saved_config, dict):
                merged_integrations[key] = {**default_config, **saved_config}
            else:
                merged_integrations[key] = saved_config or default_config
        if isinstance(saved_integrations, dict):
            for key, value in saved_integrations.items():
                if key not in merged_integrations:
                    merged_integrations[key] = value
        merged["integrations"] = merged_integrations
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_settings = dict(settings)
    safe_settings.pop("OPENAI_API_KEY", None)
    safe_settings.pop("GEMINI_API_KEY", None)
    SETTINGS_PATH.write_text(json.dumps(safe_settings, indent=2), encoding="utf-8")


def load_personality() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PERSONALITY_PATH.exists() and LEGACY_PERSONALITY_PATH.exists() and LEGACY_PERSONALITY_PATH != PERSONALITY_PATH:
        try:
            PERSONALITY_PATH.write_text(LEGACY_PERSONALITY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    if not PERSONALITY_PATH.exists():
        PERSONALITY_PATH.write_text(json.dumps(DEFAULT_PERSONALITY, indent=2), encoding="utf-8")
        return DEFAULT_PERSONALITY.copy()
    try:
        saved = json.loads(PERSONALITY_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            return {**DEFAULT_PERSONALITY, **saved}
    except Exception:
        pass
    return DEFAULT_PERSONALITY.copy()


def save_personality(personality: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_personality = {**DEFAULT_PERSONALITY, **personality}
    PERSONALITY_PATH.write_text(json.dumps(safe_personality, indent=2), encoding="utf-8")


def load_memories() -> list[dict[str, str]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_PATH.exists() and LEGACY_MEMORY_PATH.exists() and LEGACY_MEMORY_PATH != MEMORY_PATH:
        try:
            MEMORY_PATH.write_text(LEGACY_MEMORY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    if not MEMORY_PATH.exists():
        return []
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
        memories = data.get("memories", [])
        if isinstance(memories, list):
            return [memory for memory in memories if isinstance(memory, dict) and str(memory.get("text", "")).strip()]
    except Exception:
        pass
    return []


def save_memories(memories: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_memories = []
    for memory in memories[-100:]:
        text = str(memory.get("text", "")).strip()
        if not text:
            continue
        safe_memories.append(
            {
                "id": str(memory.get("id", f"mem-{int(time.time() * 1000)}")),
                "text": text[:500],
                "created_at": str(memory.get("created_at", dt.datetime.now().isoformat(timespec="seconds"))),
            }
        )
    payload = {
        "description": "Explicit JARVIS memories only. Chat transcripts are not stored here.",
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "memories": safe_memories,
    }
    MEMORY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_environment() -> None:
    candidates = [
        RESOURCE_DIR / ".env",
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        BASE_DIR.parent.parent / ".env",
        Path.cwd() / ".env",
        DATA_DIR / ".env",
    ]
    loaded_paths: set[Path] = set()
    for env_path in candidates:
        try:
            resolved = env_path.resolve()
        except Exception:
            resolved = env_path
        if resolved in loaded_paths or not env_path.exists():
            continue
        load_dotenv(env_path, override=True)
        loaded_paths.add(resolved)
    if not loaded_paths:
        load_dotenv()

    config_path = RESOURCE_DIR / "distribution_config.json"
    if config_path.exists() and not os.getenv("JARVIS_AI_PROXY_URL"):
        try:
            public_config = json.loads(config_path.read_text(encoding="utf-8"))
            proxy_url = str(public_config.get("ai_proxy_url", "")).strip()
            if proxy_url:
                os.environ["JARVIS_AI_PROXY_URL"] = proxy_url
        except (OSError, ValueError, TypeError):
            pass


def _expanded_existing_path(raw_path: str) -> Path | None:
    if not raw_path:
        return None
    expanded = Path(os.path.expandvars(raw_path)).expanduser()
    return expanded if expanded.exists() else None


def _start_menu_dirs() -> list[Path]:
    dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    return [path for path in dirs if path.exists()]


def _find_start_menu_shortcut(app_config: dict[str, Any]) -> Path | None:
    exact_names = {name.lower() for name in app_config.get("shortcuts", [])}
    contains_terms = [term.lower() for term in app_config.get("shortcut_contains", [])]

    for start_dir in _start_menu_dirs():
        for shortcut in start_dir.rglob("*.lnk"):
            name = shortcut.name.lower()
            if name in exact_names or any(term in name for term in contains_terms):
                return shortcut
    return None


def _launch_path(path: Path) -> None:
    os.startfile(str(path))  # type: ignore[attr-defined]


def app_likely_available(app_name: str, settings: dict[str, Any]) -> bool:
    key = app_name.lower().strip()
    config = SAFE_APP_LAUNCHERS.get(key)
    if not config:
        return False
    custom_path = _expanded_existing_path(str(settings.get("custom_app_paths", {}).get(key, "")))
    if custom_path is not None:
        return True
    if _find_start_menu_shortcut(config) is not None:
        return True
    for raw_path in config.get("paths", []):
        if _expanded_existing_path(str(raw_path)) is not None:
            return True
    for command in config.get("commands", []):
        if shutil.which(str(command)):
            return True
    return False


def integration_enabled(settings: dict[str, Any], key: str) -> bool:
    config = settings.get("integrations", {}).get(key, {})
    return bool(config.get("enabled", False)) if isinstance(config, dict) else False


def set_integration_enabled(settings: dict[str, Any], key: str, enabled: bool) -> None:
    integrations = dict(settings.get("integrations", {}))
    config = dict(integrations.get(key, {})) if isinstance(integrations.get(key, {}), dict) else {}
    config["enabled"] = bool(enabled)
    integrations[key] = config
    settings["integrations"] = integrations
    save_settings(settings)


def integration_status(key: str, settings: dict[str, Any]) -> tuple[str, str]:
    enabled = integration_enabled(settings, key)
    if not enabled:
        return "Disabled", "Turn it on when you want JARVIS to use it."

    env_vars = [str(name) for name in INTEGRATION_CATALOG.get(key, {}).get("env", [])]
    missing_env = [name for name in env_vars if not os.getenv(name)]

    if key == "windows_control":
        return "Ready", "Built-in Windows automation is available."
    gemini_configured = bool(os.getenv("JARVIS_AI_PROXY_URL", "").strip() or os.getenv("GEMINI_API_KEY", "").strip())
    if key == "screen_vision":
        return ("Ready", "Gemini vision is connected.") if gemini_configured else ("Offline", "AI service is not configured.")
    if key == "mouse_control":
        mode = str(settings.get("mouse_control_mode", "Safe"))
        return "Ready", f"Mouse control is in {mode} mode."
    if key == "gemini":
        model = str(settings.get("gemini_model", "gemini-2.5-flash"))
        return ("Ready", f"Using {model}.") if gemini_configured else ("Offline", "AI service is not configured.")
    if key == "openai":
        return ("Ready", "OPENAI_API_KEY is loaded.") if not missing_env else ("Needs key", "Add OPENAI_API_KEY to .env.")
    if key == "google_maps":
        return ("Ready", "GOOGLE_MAPS_API_KEY is loaded.") if not missing_env else ("Needs key", "Add GOOGLE_MAPS_API_KEY to .env.")
    if key == "browser":
        return "Ready", "Default browser can open searches and URLs."
    if key == "spotify":
        return ("Ready", "Spotify looks installed.") if app_likely_available("spotify", settings) else ("Needs app", "Install Spotify or use browser fallback.")
    if key == "apple_music":
        return ("Ready", "Apple Music looks installed.") if app_likely_available("apple music", settings) else ("Needs app", "Install Apple Music or use browser fallback.")
    if key == "phone_bridge":
        port = int(settings.get("phone_bridge_port", 8766))
        return "Configured", f"Local iPhone Shortcut receiver on port {port}."
    if key == "steam":
        game_count = len(settings.get("steam_games", {})) if isinstance(settings.get("steam_games"), dict) else 0
        return ("Ready", f"Steam found. {game_count} saved games.") if app_likely_available("steam", settings) else ("Needs app", "Install Steam or set its custom app path.")
    if key == "health_bridge":
        port = int(settings.get("health_bridge_port", 8765))
        retention = int(settings.get("health_data_retention_days", 7))
        return "Configured", f"Local Shortcut receiver on port {port}. Retention: {retention} days."
    if key == "home_assistant":
        url = os.getenv("HOME_ASSISTANT_URL") or str(settings.get("home_assistant_url", "")).strip()
        if missing_env or not url:
            return "Needs setup", "Set HOME_ASSISTANT_URL and HOME_ASSISTANT_TOKEN."
        return "Ready", "Home Assistant URL and token are configured."
    if key == "discord":
        return ("Ready", "Discord bot token is loaded.") if not missing_env else ("Needs key", "Add DISCORD_BOT_TOKEN to .env.")
    if key == "github":
        return ("Ready", "GitHub token is loaded.") if not missing_env else ("Needs key", "Add GITHUB_TOKEN to .env.")
    if key == "openweather":
        return ("Ready", "OpenWeather key is loaded.") if not missing_env else ("Needs key", "Add OPENWEATHER_API_KEY to .env.")
    if key == "todoist":
        return ("Ready", "Todoist token is loaded.") if not missing_env else ("Needs key", "Add TODOIST_API_TOKEN to .env.")
    if key == "obs":
        url = os.getenv("OBS_WEBSOCKET_URL") or str(settings.get("obs_websocket_url", "")).strip()
        return ("Ready", f"OBS WebSocket target: {url}.") if url else ("Needs setup", "Set OBS_WEBSOCKET_URL if you want remote OBS control.")
    if key == "vscode":
        return ("Ready", "VS Code looks installed.") if app_likely_available("visual studio code", settings) else ("Needs app", "Install VS Code or add it to whitelisted apps.")
    if key == "godot":
        return ("Ready", "Godot looks installed.") if app_likely_available("godot", settings) else ("Needs app", "Install Godot or add it to whitelisted apps.")
    return ("Ready", "No extra setup detected.") if not missing_env else ("Needs key", f"Add {', '.join(missing_env)} to .env.")


def press_media_play_pause() -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
    user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYEVENTF_KEYUP, 0)


def press_virtual_key(vk_code: int, presses: int = 1) -> None:
    user32 = ctypes.windll.user32
    for _ in range(max(1, int(presses))):
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


def send_safe_key(key: str) -> bool:
    safe_keys = {
        "enter": "{ENTER}",
        "return": "{ENTER}",
        "escape": "{ESC}",
        "esc": "{ESC}",
        "tab": "{TAB}",
        "space": "{SPACE}",
        "backspace": "{BACKSPACE}",
        "delete": "{DELETE}",
        "up": "{UP}",
        "down": "{DOWN}",
        "left": "{LEFT}",
        "right": "{RIGHT}",
    }
    token = safe_keys.get(key.lower().strip())
    if not token:
        return False
    if ensure_ui_automation_available() and win_keyboard is not None:
        win_keyboard.send_keys(token)
        return True
    if keyboard is not None:
        keyboard.press_and_release(key.lower().strip())
        return True
    return False


def set_volume(direction: str, amount: int = 2) -> None:
    direction = direction.lower()
    if direction == "up":
        press_virtual_key(VK_VOLUME_UP, amount)
    elif direction == "down":
        press_virtual_key(VK_VOLUME_DOWN, amount)
    elif direction == "mute":
        press_virtual_key(VK_VOLUME_MUTE, 1)


def delayed_media_play_pause(delay_seconds: int | float = 3) -> None:
    time.sleep(max(0, float(delay_seconds)))
    press_media_play_pause()


def clean_music_query_text(query: str) -> str:
    query = str(query or "").strip().strip(".")
    query = re.sub(r"^\s*(?:jarvis|hey\s+jarvis)[,\s]+", "", query, flags=re.I).strip()
    query = re.sub(r"^\s*(?:please\s+)?(?:play|start|search|find|open)\s+", "", query, flags=re.I).strip()
    query = re.sub(r"^\s*(?:apple\s+music|music\s+app|spotify|youtube\s+music|youtube)\s+(?:for\s+)?", "", query, flags=re.I).strip()
    query = re.sub(r"^\s*for\s+", "", query, flags=re.I).strip()
    query = re.sub(r"^\s*(?:the\s+)?(?:song|track|album|playlist)\s+", "", query, flags=re.I).strip()
    query = re.sub(r"^\s*(?:music\s+)?(?:called|named)\s+", "", query, flags=re.I).strip()

    service_phrases = [
        "on apple music",
        "in apple music",
        "with apple music",
        "using apple music",
        "on spotify",
        "in spotify",
        "with spotify",
        "using spotify",
        "on youtube music",
        "in youtube music",
        "with youtube music",
        "on youtube",
        "in youtube",
        "with youtube",
    ]
    for phrase in service_phrases:
        query = re.sub(re.escape(phrase), "", query, flags=re.I).strip()

    cleanup_patterns = [
        r"\b(?:you\s+)?pick(?:\s+one|\s+any(?:\s+song)?)?\b",
        r"\bchoose(?:\s+one|\s+any(?:\s+song)?)?\b",
        r"\bany\s+song\b",
        r"\bpick\s+any\s+song\b",
        r"\bsurprise\s+me\b",
        r"\bwhatever\s+you\s+want\b",
        r"\byour\s+choice\b",
        r"\brandom\s+song\b",
        r"\ba\s+song\s+by\b",
        r"\bsome\s+music\s+by\b",
        r"\banything\s+by\b",
    ]
    for pattern in cleanup_patterns:
        query = re.sub(pattern, "", query, flags=re.I).strip()

    by_match = re.match(r"(.+?)\s+by\s+(.+)$", query, flags=re.I)
    if by_match:
        title = by_match.group(1).strip(" \"'.,;:-")
        artist = by_match.group(2).strip(" \"'.,;:-")
        if title and artist:
            query = f"{title} {artist}"

    query = re.sub(r"^[,;:\-\s]+|[,;:\-\s]+$", "", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:180]


def set_windows_clipboard_text(text: str) -> bool:
    """Set clipboard text using Win32 APIs so UI automation can paste exact queries."""
    text_bytes = (text + "\0").encode("utf-16le")

    for _attempt in range(5):
        if not USER32.OpenClipboard(None):
            time.sleep(0.08)
            continue
        handle = None
        locked = None
        try:
            USER32.EmptyClipboard()
            handle = KERNEL32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
            if not handle:
                return False
            locked = KERNEL32.GlobalLock(handle)
            if not locked:
                return False
            ctypes.memmove(locked, text_bytes, len(text_bytes))
            KERNEL32.GlobalUnlock(handle)
            locked = None
            if not USER32.SetClipboardData(CF_UNICODETEXT, handle):
                return False
            handle = None
            return True
        except Exception:
            return False
        finally:
            if locked and handle:
                try:
                    KERNEL32.GlobalUnlock(handle)
                except Exception:
                    pass
            USER32.CloseClipboard()
            if handle:
                try:
                    KERNEL32.GlobalFree(handle)
                except Exception:
                    pass
    return False


def get_windows_clipboard_text() -> str:
    if not USER32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""

    for _attempt in range(5):
        if not USER32.OpenClipboard(None):
            time.sleep(0.08)
            continue
        handle = None
        locked = None
        try:
            handle = USER32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            locked = KERNEL32.GlobalLock(handle)
            if not locked:
                return ""
            return ctypes.wstring_at(locked)
        except Exception:
            return ""
        finally:
            if locked and handle:
                try:
                    KERNEL32.GlobalUnlock(handle)
                except Exception:
                    pass
            USER32.CloseClipboard()
    return ""


def paste_windows_clipboard() -> bool:
    if ensure_ui_automation_available() and win_keyboard is not None:
        win_keyboard.send_keys("^v")
        return True
    if keyboard is not None:
        keyboard.press_and_release("ctrl+v")
        return True
    return False


def send_hotkey_combo(combo: str) -> bool:
    normalized = combo.lower().replace("control", "ctrl").replace(" ", "")
    if keyboard is not None:
        keyboard.press_and_release(normalized)
        return True
    if ensure_ui_automation_available() and win_keyboard is not None:
        token_map = {
            "ctrl+a": "^a",
            "ctrl+c": "^c",
            "ctrl+v": "^v",
            "ctrl+f": "^f",
        }
        token = token_map.get(normalized)
        if token:
            win_keyboard.send_keys(token)
            return True
    return False


def capture_active_document_text() -> tuple[bool, str, str]:
    previous_clipboard = get_windows_clipboard_text()
    if not send_hotkey_combo("ctrl+a"):
        return False, "", "Could not send Ctrl+A to select the document."
    time.sleep(0.35)
    if not send_hotkey_combo("ctrl+c"):
        if previous_clipboard:
            set_windows_clipboard_text(previous_clipboard)
        return False, "", "Could not send Ctrl+C to copy the document."
    time.sleep(0.7)
    text = get_windows_clipboard_text().strip()
    if previous_clipboard:
        set_windows_clipboard_text(previous_clipboard)
    else:
        set_windows_clipboard_text("")
    if not text:
        return False, "", "I copied from the active window, but no plain text came back."
    return True, text, f"Captured {len(text.split())} words from the active document."


def chunk_text_for_tts(text: str, max_chars: int = 850) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    if not cleaned:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", cleaned) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = re.split(r"(?<=[.!?])\s+", paragraph)
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                for index in range(0, len(piece), max_chars):
                    chunks.append(piece[index : index + max_chars].strip())
                continue
            if current and len(current) + len(piece) + 1 > max_chars:
                chunks.append(current.strip())
                current = piece
            else:
                current = f"{current} {piece}".strip()
        if current and len(current) + 2 <= max_chars:
            current = f"{current}\n".strip()
    if current:
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]


def active_window_handle() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def screen_size() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    return int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))


def clamp_screen_point(x: int, y: int) -> tuple[int, int]:
    width, height = screen_size()
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def move_mouse_to(x: int, y: int) -> tuple[int, int]:
    x, y = clamp_screen_point(int(x), int(y))
    start_x, start_y = mouse_position()
    dx = x - start_x
    dy = y - start_y
    distance = (dx * dx + dy * dy) ** 0.5
    steps = max(8, min(70, int(distance / 18)))
    user32 = ctypes.windll.user32
    for step in range(1, steps + 1):
        progress = step / steps
        eased = progress * progress * (3 - 2 * progress)
        next_x = round(start_x + dx * eased)
        next_y = round(start_y + dy * eased)
        user32.SetCursorPos(next_x, next_y)
        time.sleep(0.006)
    user32.SetCursorPos(x, y)
    return x, y


def mouse_position() -> tuple[int, int]:
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return int(point.x), int(point.y)


def move_mouse_relative(direction: str, pixels: int = 120) -> tuple[int, int]:
    x, y = mouse_position()
    direction = direction.lower()
    pixels = max(1, min(1000, int(pixels)))
    if direction == "left":
        x -= pixels
    elif direction == "right":
        x += pixels
    elif direction == "up":
        y -= pixels
    elif direction == "down":
        y += pixels
    return move_mouse_to(x, y)


def click_mouse(x: int | None = None, y: int | None = None, button: str = "left", double: bool = False) -> None:
    user32 = ctypes.windll.user32
    if x is not None and y is not None:
        move_mouse_to(x, y)
    down, up = (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP) if button == "right" else (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
    repeats = 2 if double else 1
    for _ in range(repeats):
        user32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.04)
        user32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.08)


def scroll_mouse(direction: str, amount: int = 5) -> None:
    delta = 120 * max(1, int(amount))
    if direction.lower() == "down":
        delta *= -1
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)


def set_active_window_state(state: str) -> bool:
    handle = active_window_handle()
    if not handle:
        return False
    command = {
        "minimize": SW_SHOWMINIMIZED,
        "maximize": SW_SHOWMAXIMIZED,
        "restore": SW_RESTORE,
    }.get(state)
    if command is None:
        return False
    return bool(ctypes.windll.user32.ShowWindow(handle, command))


def close_active_window() -> bool:
    handle = active_window_handle()
    if not handle:
        return False
    WM_CLOSE = 0x0010
    return bool(ctypes.windll.user32.PostMessageW(handle, WM_CLOSE, 0, 0))


def list_visible_windows(limit: int = 12) -> list[dict[str, Any]]:
    user32 = ctypes.windll.user32
    windows: list[dict[str, Any]] = []

    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        title = title_buffer.value.strip()
        if title:
            windows.append({"handle": hwnd, "title": title})
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    return windows[:limit]


def focus_window_by_title(query: str) -> str | None:
    lowered = query.lower().strip()
    if not lowered:
        return None
    user32 = ctypes.windll.user32
    for window in list_visible_windows(limit=50):
        title = str(window["title"])
        if lowered in title.lower():
            hwnd = int(window["handle"])
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return title
    return None


def lock_windows_workstation() -> bool:
    return bool(ctypes.windll.user32.LockWorkStation())


def clear_recycle_bin() -> tuple[bool, str]:
    try:
        result = ctypes.windll.shell32.SHEmptyRecycleBinW(
            None,
            None,
            SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND,
        )
    except Exception as exc:
        return False, f"Windows Recycle Bin API failed: {exc}"
    if result == 0:
        return True, "Recycle Bin cleared."
    return False, f"Windows refused to clear the Recycle Bin. Error code: {result}"


def internet_is_online(timeout: float = 2.0) -> bool:
    targets = [
        ("1.1.1.1", 443),
        ("8.8.8.8", 443),
        ("www.google.com", 443),
    ]
    successes = 0
    for host, port in targets:
        try:
            socket.create_connection((host, port), timeout=timeout).close()
            successes += 1
            if successes >= 1:
                return True
        except OSError:
            continue
    return False


def get_system_snapshot() -> dict[str, Any]:
    battery = psutil.sensors_battery()
    disk = psutil.disk_usage(str(Path.home().anchor or "C:\\"))
    snapshot: dict[str, Any] = {
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disk": disk.percent,
        "battery_percent": None,
        "battery_plugged": None,
        "online": internet_is_online(timeout=1.2),
        "active_window": get_active_window_title(),
    }
    if battery is not None:
        snapshot["battery_percent"] = float(battery.percent)
        snapshot["battery_plugged"] = bool(battery.power_plugged)
    return snapshot


def format_system_snapshot(snapshot: dict[str, Any]) -> str:
    battery_percent = snapshot.get("battery_percent")
    if battery_percent is None:
        battery_text = "Battery: unavailable"
    else:
        plugged = "plugged in" if snapshot.get("battery_plugged") else "on battery"
        battery_text = f"Battery: {battery_percent:.0f}% {plugged}"
    online_text = "Online" if snapshot.get("online") else "Offline"
    return (
        f"CPU {snapshot.get('cpu', 0):.0f}% | RAM {snapshot.get('ram', 0):.0f}% | "
        f"Disk {snapshot.get('disk', 0):.0f}% | {battery_text} | {online_text}"
    )


def current_time_in_quiet_hours(settings: dict[str, Any]) -> bool:
    if not settings.get("awareness_quiet_hours_enabled", False):
        return False

    def parse_clock(value: str) -> dt.time | None:
        try:
            return dt.datetime.strptime(str(value).strip(), "%H:%M").time()
        except ValueError:
            return None

    start = parse_clock(str(settings.get("awareness_quiet_hours_start", "22:00")))
    end = parse_clock(str(settings.get("awareness_quiet_hours_end", "08:00")))
    if start is None or end is None:
        return False
    now = dt.datetime.now().time()
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def known_folder_path(name: str) -> Path | None:
    home = Path.home()
    folders = {
        "desktop": home / "Desktop",
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "pictures": home / "Pictures",
        "music": home / "Music",
        "videos": home / "Videos",
        "screenshots": SCREENSHOTS_DIR,
        "project": BASE_DIR,
        "jarvis": BASE_DIR,
    }
    return folders.get(name.lower().strip())


def safe_folder_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().strip(".")
    return re.sub(r"\s+", " ", name)[:80]


def normalize_watch_folder(path_text: str) -> Path | None:
    if not path_text.strip():
        return None
    path = Path(os.path.expandvars(os.path.expanduser(path_text.strip().strip('"'))))
    try:
        path = path.resolve()
    except Exception:
        path = path.absolute()
    if path.exists() and path.is_dir():
        return path
    return None


def is_watchable_project_file(path: Path, settings: dict[str, Any]) -> bool:
    skip_parts = {
        ".git",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        ".godot",
        "dist",
        "build",
        ".pyinstaller_work",
        ".pyinstaller_work3",
    }
    if any(part.lower() in skip_parts for part in path.parts):
        return False
    allowed = {str(ext).lower() for ext in settings.get("project_watch_extensions", [])}
    if path.suffix.lower() not in allowed:
        return False
    try:
        stat = path.stat()
    except OSError:
        return False
    return path.is_file() and stat.st_size <= 2_000_000


def read_text_tail(path: Path, max_bytes: int = 24000) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(max(0, size - max_bytes))
            data = handle.read(max_bytes)
    except OSError:
        return ""
    return data.decode("utf-8", errors="ignore")


CODING_FILE_EXTENSIONS = {
    ".py", ".pyw", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss",
    ".json", ".md", ".toml", ".yaml", ".yml", ".xml", ".sql", ".sh", ".ps1",
    ".gd", ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".java", ".kt", ".rs",
    ".go", ".rb", ".php", ".swift", ".vue", ".svelte", ".ini", ".cfg", ".env.example",
}

CODING_SKIP_FOLDERS = {
    ".git", ".idea", ".vscode", ".venv", "venv", "env", "__pycache__",
    "node_modules", ".godot", "dist", "build", "coverage", ".pytest_cache",
    ".mypy_cache", ".next", ".nuxt", "target", "vendor", ".jarvis_backups",
}


def coding_workspace_files(root: Path, query: str = "", limit: int = 800) -> list[Path]:
    """Return readable source files under root while skipping generated dependency trees."""
    root = root.resolve()
    lowered_query = query.strip().lower()
    matches: list[Path] = []
    try:
        candidates = root.rglob("*")
        for path in candidates:
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if any(part.lower() in CODING_SKIP_FOLDERS for part in relative.parts[:-1]):
                continue
            if not path.is_file() or path.stat().st_size > 1_500_000:
                continue
            suffix = path.suffix.lower()
            if suffix not in CODING_FILE_EXTENSIONS and path.name.lower() not in {
                "dockerfile", "makefile", "requirements.txt", "package.json", "pyproject.toml",
            }:
                continue
            if lowered_query:
                relative_text = str(relative).lower()
                if lowered_query not in relative_text:
                    try:
                        size = path.stat().st_size
                        with path.open("rb") as handle:
                            sample_data = handle.read(180000)
                            if size > 180000:
                                handle.seek(max(0, size - 60000))
                                sample_data += handle.read(60000)
                        sample = sample_data.decode("utf-8", errors="ignore").lower()
                    except OSError:
                        continue
                    if lowered_query not in sample:
                        continue
            matches.append(path)
            if len(matches) >= max(20, min(limit, 2000)):
                break
    except OSError:
        pass
    return sorted(matches, key=lambda item: str(item.relative_to(root)).lower())


def safe_coding_workspace_file(root: Path, candidate: Path) -> Path | None:
    try:
        resolved_root = root.resolve()
        resolved = candidate.resolve()
        resolved.relative_to(resolved_root)
    except (OSError, ValueError):
        return None
    if not resolved.is_file() or resolved.stat().st_size > 1_500_000:
        return None
    return resolved


def is_agent_readable_code_file(path: Path) -> bool:
    name = path.name.lower()
    blocked_names = {".env", ".env.local", ".env.production", ".env.development", "credentials.json", "secrets.json"}
    blocked_suffixes = {".pem", ".key", ".pfx", ".p12", ".kdbx"}
    if name in blocked_names or path.suffix.lower() in blocked_suffixes:
        return False
    if any(term in name for term in ["credential", "private_key", "private-key"]):
        return False
    allowed_names = {"dockerfile", "makefile", "requirements.txt", "package.json", "pyproject.toml"}
    return path.suffix.lower() in CODING_FILE_EXTENSIONS or name in allowed_names


def redact_code_secrets(text: str) -> str:
    assignment = re.compile(
        r'''(?i)(["']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|passwd)["']?[ \t]*(?:=|:)[ \t]*)(["'][^"'\r\n]*["']|[^,\s}\r\n]+)'''
    )
    return assignment.sub(lambda match: match.group(1) + "[REDACTED]", text)

def read_coding_file(path: Path, max_chars: int = 120000) -> tuple[bool, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return False, f"Could not read file: {exc}"
    if b"\x00" in data[:4096]:
        return False, "That appears to be a binary file, so I left it alone."
    text = data.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Preview truncated]"
    return True, text

def apply_code_edit_with_backup(
    root: Path,
    path: Path,
    updated_content: str,
    expected_hash: str,
    newline: str,
) -> tuple[bool, str, Path | None]:
    safe_path = safe_coding_workspace_file(root, path)
    if safe_path is None:
        return False, "The target file is outside the coding workspace.", None
    temp_path: Path | None = None
    try:
        current_bytes = safe_path.read_bytes()
        if hashlib.sha256(current_bytes).hexdigest() != expected_hash:
            return False, "The file changed after the proposal was created.", None
        resolved_root = root.resolve()
        backup_root = resolved_root / ".jarvis_backups"
        if backup_root.exists() and backup_root.is_symlink():
            return False, "The backup folder is a symbolic link, so JARVIS refused to write through it.", None
        backup_root.mkdir(parents=True, exist_ok=True)
        try:
            backup_root.resolve().relative_to(resolved_root)
        except ValueError:
            return False, "The backup folder resolves outside the coding workspace.", None
        backup_base = backup_root / safe_path.relative_to(resolved_root)
        backup_base.parent.mkdir(parents=True, exist_ok=True)
        try:
            backup_base.parent.resolve().relative_to(backup_root.resolve())
        except ValueError:
            return False, "The backup destination resolves outside the backup folder.", None
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_base.with_name(f"{backup_base.name}.{timestamp}.bak")
        shutil.copy2(safe_path, backup_path)
        output = updated_content.replace("\r\n", "\n").replace("\r", "\n")
        if newline == "\r\n":
            output = output.replace("\n", "\r\n")
        temp_path = safe_path.with_name(f".{safe_path.name}.{timestamp}.jarvis.tmp")
        temp_path.write_bytes(output.encode("utf-8"))
        os.replace(temp_path, safe_path)
        return True, "Code edit applied.", backup_path
    except Exception as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False, f"The code edit was not applied: {exc}", None

def detect_coding_project_type(root: Path) -> str:
    markers = [
        ("project.godot", "Godot"),
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("package.json", "Node.js"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("pom.xml", "Java"),
    ]
    for marker, label in markers:
        if (root / marker).exists():
            return label
    if any(root.glob("*.sln")) or any(root.glob("*.csproj")):
        return ".NET"
    return "General source project"


def diagnose_coding_workspace(root: Path, limit: int = 800) -> dict[str, Any]:
    root = root.resolve()
    files = coding_workspace_files(root, limit=limit)
    issues: list[dict[str, Any]] = []
    extension_counts: dict[str, int] = {}
    for path in files:
        relative = str(path.relative_to(root))
        extension = path.suffix.lower() or "[none]"
        extension_counts[extension] = extension_counts.get(extension, 0) + 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append({"file": relative, "line": 0, "kind": "read", "message": f"Could not read UTF-8 source: {exc}"})
            continue
        source_lines = text.splitlines()
        conflict_start = next(
            (index for index, value in enumerate(source_lines, 1) if value.lstrip().startswith("<<<<<<< ")),
            0,
        )
        has_separator = any(value.lstrip() == "=======" for value in source_lines)
        has_conflict_end = any(value.lstrip().startswith(">>>>>>> ") for value in source_lines)
        if conflict_start and has_separator and has_conflict_end:
            issues.append({"file": relative, "line": conflict_start, "kind": "merge", "message": "Unresolved merge-conflict markers."})
        try:
            if path.suffix.lower() in {".py", ".pyw"}:
                ast.parse(text, filename=relative)
            elif path.suffix.lower() == ".json":
                json.loads(text)
            elif path.suffix.lower() == ".toml":
                tomllib.loads(text)
        except (SyntaxError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
            line = int(getattr(exc, "lineno", 0) or 0)
            issues.append({"file": relative, "line": line, "kind": "syntax", "message": str(exc)[:300]})
    language_summary = sorted(extension_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "project_type": detect_coding_project_type(root),
        "file_count": len(files),
        "languages": language_summary,
        "issues": issues,
        "truncated": len(files) >= max(20, min(limit, 2000)),
    }


def format_coding_diagnostics(report: dict[str, Any]) -> str:
    lines = [
        f"PROJECT: {report.get('project_type', 'Unknown')}",
        f"SOURCE FILES SCANNED: {report.get('file_count', 0)}",
    ]
    languages = report.get("languages", [])
    if languages:
        lines.append("FILE TYPES: " + ", ".join(f"{ext} ({count})" for ext, count in languages[:12]))
    if report.get("truncated"):
        lines.append("NOTE: Scan reached the configured file limit.")
    issues = report.get("issues", [])
    lines.append("")
    if not issues:
        lines.append("No supported syntax errors or unresolved merge markers found.")
    else:
        lines.append(f"ISSUES ({len(issues)}):")
        for issue in issues[:200]:
            location = f":{issue.get('line')}" if issue.get("line") else ""
            lines.append(f"- {issue.get('file')}{location} [{issue.get('kind')}] {issue.get('message')}")
        if len(issues) > 200:
            lines.append(f"...and {len(issues) - 200} more issues.")
    return "\n".join(lines)

def _python_runner_prefix() -> list[str] | None:
    if not getattr(sys, "frozen", False):
        return [sys.executable]
    python_exe = shutil.which("python.exe") or shutil.which("python")
    if python_exe:
        return [python_exe]
    py_launcher = shutil.which("py.exe") or shutil.which("py")
    return [py_launcher, "-3"] if py_launcher else None


_PYTHON_MODULE_AVAILABILITY: dict[tuple[str, ...], bool] = {}


def _python_module_available(prefix: list[str], module: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.]+", module):
        return False
    key = (*prefix, module)
    if key in _PYTHON_MODULE_AVAILABILITY:
        return _PYTHON_MODULE_AVAILABILITY[key]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            [*prefix, "-c", f"import {module}"],
            capture_output=True,
            timeout=4,
            shell=False,
            env=sanitized_runner_environment(),
            creationflags=flags,
        )
        available = result.returncode == 0
    except Exception:
        available = False
    _PYTHON_MODULE_AVAILABILITY[key] = available
    return available


def stop_process_tree(process_id: int) -> None:
    try:
        parent = psutil.Process(process_id)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.Error:
                pass
        try:
            parent.kill()
        except psutil.Error:
            pass
        psutil.wait_procs([*children, parent], timeout=5)
    except (psutil.Error, OSError):
        pass

def approved_code_runners(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    runners: list[dict[str, Any]] = []
    python_prefix = _python_runner_prefix()
    has_python = any(root.glob("*.py")) or (root / "pyproject.toml").exists() or (root / "requirements.txt").exists()
    if has_python and python_prefix:
        runners.append({
            "id": "python_compile",
            "label": "Python syntax check",
            "risk": "medium",
            "command": [*python_prefix, "-m", "compileall", "-q", "."],
        })
        has_tests = (root / "tests").is_dir() or (root / "pytest.ini").exists() or any(root.glob("test_*.py"))
        if has_tests:
            runners.append({
                "id": "python_unittest",
                "label": "Python tests (unittest)",
                "risk": "high",
                "command": [*python_prefix, "-m", "unittest", "discover", "-v"],
            })
        if has_tests and _python_module_available(python_prefix, "pytest"):
            runners.append({
                "id": "python_pytest",
                "label": "Python tests (pytest)",
                "risk": "high",
                "command": [*python_prefix, "-m", "pytest", "-q"],
            })
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if (root / "package.json").exists() and npm:
        runners.append({"id": "node_test", "label": "Node tests (npm test)", "risk": "high", "command": [npm, "test"]})
    godot = shutil.which("godot.exe") or shutil.which("godot4.exe") or shutil.which("godot") or shutil.which("godot4")
    if (root / "project.godot").exists() and godot:
        runners.append({
            "id": "godot_headless",
            "label": "Godot headless project check",
            "risk": "high",
            "command": [godot, "--headless", "--path", ".", "--editor", "--quit"],
        })
    dotnet = shutil.which("dotnet.exe") or shutil.which("dotnet")
    if dotnet and (any(root.glob("*.sln")) or any(root.glob("*.csproj"))):
        runners.append({"id": "dotnet_test", "label": ".NET tests", "risk": "high", "command": [dotnet, "test", "--nologo"]})
    cargo = shutil.which("cargo.exe") or shutil.which("cargo")
    if cargo and (root / "Cargo.toml").exists():
        runners.append({"id": "cargo_test", "label": "Rust tests (cargo)", "risk": "high", "command": [cargo, "test", "--quiet"]})
    go = shutil.which("go.exe") or shutil.which("go")
    if go and (root / "go.mod").exists():
        runners.append({"id": "go_test", "label": "Go tests", "risk": "high", "command": [go, "test", "./..."]})
    return runners


def sanitized_runner_environment() -> dict[str, str]:
    environment = dict(os.environ)
    sensitive_terms = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "PRIVATE_KEY")
    for key in list(environment):
        if any(term in key.upper() for term in sensitive_terms):
            environment.pop(key, None)
    return environment


def run_approved_code_runner(root: Path, runner_id: str, timeout_seconds: int = 120) -> dict[str, Any]:
    root = root.resolve()
    runner = next((item for item in approved_code_runners(root) if item["id"] == runner_id), None)
    if runner is None:
        return {"ok": False, "output": "That runner is unavailable or not approved for this project.", "risk": "high", "label": runner_id}
    command = [str(part) for part in runner["command"]]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=str(root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            shell=False,
            env=sanitized_runner_environment(),
            creationflags=flags,
        )
        try:
            stdout, stderr = process.communicate(timeout=max(5, min(int(timeout_seconds), 600)))
        except subprocess.TimeoutExpired:
            stop_process_tree(process.pid)
            stdout, stderr = process.communicate(timeout=5)
            output = "\n".join(part.strip() for part in [stdout, stderr] if part and part.strip())
            return {"ok": False, "output": f"Runner timed out and its process tree was stopped.\n{output}".strip(), "returncode": None, "duration": round(time.monotonic() - started, 2), "risk": runner["risk"], "label": runner["label"]}
        combined = "\n".join(part.strip() for part in [stdout, stderr] if part and part.strip())
        if not combined:
            combined = "Runner completed without console output."
        if len(combined) > 60000:
            combined = "[Earlier runner output truncated]\n" + combined[-60000:]
        return {
            "ok": process.returncode == 0,
            "output": combined,
            "returncode": process.returncode,
            "duration": round(time.monotonic() - started, 2),
            "risk": runner["risk"],
            "label": runner["label"],
        }
    except Exception as exc:
        return {"ok": False, "output": f"Runner failed to start: {exc}", "returncode": None, "duration": round(time.monotonic() - started, 2), "risk": runner["risk"], "label": runner["label"]}

def detect_error_in_text(text: str, settings: dict[str, Any]) -> str | None:
    if not text.strip():
        return None
    lowered = text.lower()
    terms = [str(term).lower() for term in settings.get("project_watch_error_terms", []) if str(term).strip()]
    if not any(term in lowered for term in terms):
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines[-80:]):
        lowered_line = line.lower()
        if any(term in lowered_line for term in terms):
            return line[:260]
    return lines[-1][:260] if lines else "A watched file contains an error term."


def list_known_folder_files(folder_name: str, limit: int = 12) -> list[Path]:
    folder = known_folder_path(folder_name)
    if folder is None or not folder.exists():
        return []
    items = [path for path in folder.iterdir() if not path.name.startswith(".")]
    items.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    return items[:limit]


def open_recent_file_from_folder(folder_name: str) -> Path | None:
    for path in list_known_folder_files(folder_name, limit=30):
        if path.is_file():
            _launch_path(path)
            return path
    return None


def ensure_ui_automation_available() -> bool:
    global Desktop, win_keyboard, _PYWINAUTO_ATTEMPTED
    if Desktop is not None and win_keyboard is not None:
        return True
    if _PYWINAUTO_ATTEMPTED:
        return False

    _PYWINAUTO_ATTEMPTED = True
    try:
        COMTYPES_GEN_DIR.mkdir(parents=True, exist_ok=True)
        import comtypes.client

        comtypes.client.gen_dir = str(COMTYPES_GEN_DIR)
        from pywinauto import Desktop as PywinautoDesktop
        from pywinauto import keyboard as pywinauto_keyboard

        Desktop = PywinautoDesktop
        win_keyboard = pywinauto_keyboard
        return True
    except Exception:
        Desktop = None
        win_keyboard = None
        return False


def _find_apple_music_window(timeout_seconds: int = 10) -> Any | None:
    if not ensure_ui_automation_available():
        return None
    if Desktop is None:
        return None

    end_time = time.time() + timeout_seconds
    while time.time() < end_time:
        try:
            desktop = Desktop(backend="uia")
            for window in desktop.windows():
                title = window.window_text().lower()
                if "apple music" in title or title == "music":
                    return window
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _click_first_apple_music_play_button(window: Any) -> bool:
    play_words = ("play", "preview")
    skip_words = ("airplay", "display", "replay")

    try:
        buttons = window.descendants(control_type="Button")
    except Exception:
        return False

    for button in buttons:
        try:
            label = button.window_text().strip().lower()
            if not label:
                label = str(button.element_info.name or "").strip().lower()
            if not any(word in label for word in play_words):
                continue
            if any(word in label for word in skip_words):
                continue
            if not button.is_visible() or not button.is_enabled():
                continue
            rectangle = button.rectangle()
            if rectangle.top < window.rectangle().top + 120:
                continue
            try:
                button.invoke()
            except Exception:
                button.click_input()
            return True
        except Exception:
            continue
    return False


def _apple_music_query_terms(query: str) -> list[str]:
    lowered = re.sub(r"[^a-z0-9\s]", " ", query.lower())
    stop_words = {"a", "an", "and", "by", "for", "from", "in", "on", "the", "to", "with"}
    return [term for term in lowered.split() if len(term) > 1 and term not in stop_words]


def _score_apple_music_result(text: str, query: str) -> int:
    lowered = text.lower()
    terms = _apple_music_query_terms(query)
    if not terms:
        return 0
    score = 0
    for term in terms:
        if term in lowered:
            score += 3 if len(term) > 3 else 2
    compact_query = " ".join(terms)
    if compact_query and compact_query in lowered:
        score += 8
    if "michael" in terms and "jackson" in terms and "michael jackson" in lowered:
        score += 10
    if "bad" in terms and re.search(r"\bbad\b", lowered):
        score += 6
    return score


def _click_best_apple_music_result(window: Any, query: str) -> tuple[bool, str]:
    """Click the best visible result row that actually matches the requested query."""
    try:
        window_rectangle = window.rectangle()
        controls = window.descendants()
    except Exception:
        return False, "Apple Music did not expose searchable UI controls."

    row_texts: dict[int, dict[str, Any]] = {}
    for control in controls:
        try:
            info = control.element_info
            control_type = str(info.control_type or "")
            if control_type not in {"DataItem", "ListItem", "Text"}:
                continue
            if not control.is_visible() or not control.is_enabled():
                continue

            rectangle = control.rectangle()
            if rectangle.top < window_rectangle.top + 190:
                continue
            if rectangle.left < window_rectangle.left + 120:
                continue
            if rectangle.width() < 80 or rectangle.height() < 12:
                continue

            text = (control.window_text() or str(info.name or "")).strip()
            lowered = text.lower()
            if not text or lowered in {"songs", "albums", "artists", "playlists", "search"}:
                continue
            if any(word in lowered for word in ["library", "home", "browse", "radio", "listen now"]):
                continue

            row_key = round(rectangle.top / 24) * 24
            row = row_texts.setdefault(row_key, {"top": rectangle.top, "left": rectangle.left, "texts": [], "control": control})
            row["texts"].append(text)
            if rectangle.left < row["left"]:
                row["left"] = rectangle.left
                row["control"] = control
        except Exception:
            continue

    candidates = []
    for row in row_texts.values():
        combined = " ".join(dict.fromkeys(row["texts"]))
        score = _score_apple_music_result(combined, query)
        if score > 0:
            candidates.append((score, row["top"], row["left"], combined, row["control"]))

    if not candidates:
        return False, "I could not find a visible Apple Music result matching the requested song or artist."

    score, _top, _left, combined_text, best_control = sorted(candidates, key=lambda item: (-item[0], item[1], item[2]))[0]
    minimum_score = 9 if len(_apple_music_query_terms(query)) >= 2 else 5
    if score < minimum_score:
        return False, f"The best visible result was too weak a match: {combined_text[:120]}"

    try:
        best_control.click_input(double=True)
    except Exception:
        try:
            best_control.click_input()
            if win_keyboard is not None:
                win_keyboard.send_keys("{ENTER}")
        except Exception:
            return False, f"I found a likely result but could not activate it: {combined_text[:120]}"
    return True, combined_text[:160]


def apple_music_search_and_press_play(query: str, settings: dict[str, Any]) -> tuple[bool, str]:
    launch_allowed_app("apple music", settings)
    window = _find_apple_music_window()
    if window is None or win_keyboard is None:
        return False, "I opened Apple Music, but could not attach to its window, so I did not press play on a random queued track."

    try:
        window.set_focus()
        time.sleep(0.4)
        win_keyboard.send_keys("^f")
        time.sleep(0.2)
        win_keyboard.send_keys("^a{BACKSPACE}")
        time.sleep(0.1)
        if set_windows_clipboard_text(query):
            win_keyboard.send_keys("^v")
        else:
            win_keyboard.send_keys(query, with_spaces=True, pause=0.03)
        win_keyboard.send_keys("{ENTER}")
        wait_seconds = float(settings.get("apple_music_result_wait_seconds", 4))
        time.sleep(max(1.0, min(10.0, wait_seconds)))
        clicked_result = False
        matched_result = ""
        if settings.get("apple_music_text_match_click", False):
            clicked_result, matched_result = _click_best_apple_music_result(window, query)
            time.sleep(1)
            if clicked_result:
                return True, f"I searched Apple Music for '{query}' and opened the matched result: {matched_result}."
            if matched_result:
                return False, (
                    f"I searched Apple Music for '{query}', but I did not find a verified matching result. "
                    f"{matched_result} I refused to press Play on a mystery song."
                )
    except Exception as exc:
        return False, f"I tried to search Apple Music for '{query}', but UI automation complained: {exc}"

    return False, (
        f"I searched Apple Music for '{query}', but could not verify a matching result. "
        "I did not press Play because that can start the wrong queued song."
    )


def launch_allowed_app(target: str, settings: dict[str, Any]) -> tuple[bool, str]:
    normalized = target.strip().lower()
    app_name = None
    app_config: dict[str, Any] | None = None

    for name, config in SAFE_APP_LAUNCHERS.items():
        aliases = [alias.lower() for alias in config.get("aliases", [])]
        if normalized == name or normalized in aliases:
            app_name = name
            app_config = config
            break

    if app_name is None:
        for custom_app in settings.get("custom_whitelisted_apps", []):
            custom_name = str(custom_app.get("name", "")).strip().lower()
            aliases = [str(alias).strip().lower() for alias in custom_app.get("aliases", [])]
            if normalized == custom_name or normalized in aliases:
                app_name = custom_name
                app_config = {"paths": [str(custom_app.get("path", ""))]}
                break

    if app_name is None or app_config is None:
        return False, f"I can only open whitelisted apps or known sites. '{target}' is not on the list."

    custom_paths = settings.get("custom_app_paths", {})
    custom_path = _expanded_existing_path(str(custom_paths.get(app_name, "")))
    if custom_path:
        _launch_path(custom_path)
        return True, f"Opening {app_name.title()} from your custom path."

    if app_config.get("prefer_app_ids"):
        for app_id in app_config.get("app_ids", []):
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
            return True, f"Opening {app_name.title()} from Microsoft Store apps."

    if app_config.get("prefer_commands"):
        for command in app_config.get("commands", []):
            if shutil.which(command):
                subprocess.Popen([command], shell=False)
                return True, f"Opening {app_name.title()}."

    for raw_path in app_config.get("paths", []):
        found_path = _expanded_existing_path(raw_path)
        if found_path:
            _launch_path(found_path)
            return True, f"Opening {app_name.title()}."

    shortcut = _find_start_menu_shortcut(app_config)
    if shortcut:
        _launch_path(shortcut)
        return True, f"Opening {app_name.title()} from the Start Menu."

    if not app_config.get("prefer_commands"):
        for command in app_config.get("commands", []):
            if shutil.which(command):
                subprocess.Popen([command], shell=False)
                return True, f"Opening {app_name.title()}."

    for app_id in app_config.get("app_ids", []):
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
        return True, f"Opening {app_name.title()} from Microsoft Store apps."

    for uri in app_config.get("uris", []):
        webbrowser.open(uri)
        return True, f"Opening {app_name.title()}."

    return False, (
        f"I couldn't find {app_name.title()} on this PC. Add its full .exe or .lnk path to "
        f"settings.json under custom_app_paths -> {app_name}."
    )


def _normalize_lookup_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _find_steam_executable(settings: dict[str, Any]) -> Path | None:
    custom_path = _expanded_existing_path(str(settings.get("custom_app_paths", {}).get("steam", "")))
    if custom_path:
        return custom_path

    for raw_path in SAFE_APP_LAUNCHERS.get("steam", {}).get("paths", []):
        found_path = _expanded_existing_path(raw_path)
        if found_path:
            return found_path

    command_path = shutil.which("steam")
    if command_path:
        return Path(command_path)

    registry_paths = [
        r"HKCU\Software\Valve\Steam",
        r"HKLM\SOFTWARE\WOW6432Node\Valve\Steam",
        r"HKLM\SOFTWARE\Valve\Steam",
    ]
    try:
        import winreg

        for registry_path in registry_paths:
            root_name, subkey = registry_path.split("\\", 1)
            root = winreg.HKEY_CURRENT_USER if root_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for value_name in ["SteamExe", "InstallPath", "SteamPath"]:
                        try:
                            value, _value_type = winreg.QueryValueEx(key, value_name)
                            candidate = Path(str(value).replace("/", "\\"))
                            if candidate.is_dir():
                                candidate = candidate / "steam.exe"
                            if candidate.exists():
                                return candidate
                        except OSError:
                            continue
            except OSError:
                continue
    except Exception:
        pass

    return None


def _open_steam_uri(app_id: str) -> None:
    uri = f"steam://rungameid/{app_id}"
    try:
        os.startfile(uri)  # type: ignore[attr-defined]
    except Exception:
        webbrowser.open(uri)


def _parse_vdf_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for match in re.finditer(r'"([^"]+)"\s+"([^"]*)"', text):
        values[match.group(1).strip()] = match.group(2).strip()
    return values


def _steam_root_candidates(settings: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    steam_exe = _find_steam_executable(settings)
    if steam_exe:
        candidates.append(steam_exe.parent)

    for raw_path in SAFE_APP_LAUNCHERS.get("steam", {}).get("paths", []):
        found_path = _expanded_existing_path(raw_path)
        if found_path:
            candidates.append(found_path.parent)

    return list(dict.fromkeys(candidates))


def _steam_library_folders(settings: dict[str, Any]) -> list[Path]:
    folders: list[Path] = []
    for steam_root in _steam_root_candidates(settings):
        if steam_root.exists():
            folders.append(steam_root)
        library_file = steam_root / "steamapps" / "libraryfolders.vdf"
        if not library_file.exists():
            continue
        try:
            text = library_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw_path in re.findall(r'"path"\s+"([^"]+)"', text):
            folder = Path(raw_path.replace("\\\\", "\\"))
            if folder.exists():
                folders.append(folder)
    return list(dict.fromkeys(folders))


def import_steam_library(settings: dict[str, Any]) -> tuple[int, dict[str, str]]:
    imported: dict[str, str] = {}
    for library_folder in _steam_library_folders(settings):
        steamapps = library_folder / "steamapps"
        if not steamapps.exists():
            continue
        for manifest in steamapps.glob("appmanifest_*.acf"):
            try:
                values = _parse_vdf_key_values(manifest.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            app_id = values.get("appid", "").strip()
            name = values.get("name", "").strip()
            state_flags = values.get("StateFlags", "")
            if not app_id.isdigit() or not name:
                continue
            if state_flags and state_flags == "0":
                continue
            imported[name] = app_id

    existing = dict(settings.get("steam_games", {}))
    before = len(existing)
    existing.update(imported)
    settings["steam_games"] = dict(sorted(existing.items(), key=lambda item: item[0].lower()))
    save_settings(settings)
    return max(0, len(existing) - before), imported


def launch_steam_game(game_name: str, settings: dict[str, Any]) -> tuple[bool, str]:
    requested = game_name.strip(" .,!?:;\"'")
    if not requested:
        return False, "Tell me which Steam game to launch. Even I require nouns."

    steam_games = settings.get("steam_games", {})
    normalized_requested = _normalize_lookup_name(requested)

    for configured_name, app_id in steam_games.items():
        normalized_name = _normalize_lookup_name(str(configured_name))
        if normalized_requested == normalized_name:
            app_id_text = str(app_id).strip()
            if not app_id_text.isdigit():
                return False, f"The Steam App ID for {configured_name} is not valid. It should be numbers only."
            steam_exe = _find_steam_executable(settings)
            if steam_exe:
                subprocess.Popen([str(steam_exe), "-applaunch", app_id_text], shell=False)
                return True, f"Launching {configured_name} through Steam with App ID {app_id_text}."
            _open_steam_uri(app_id_text)
            return True, f"Launching {configured_name} through Steam URI with App ID {app_id_text}."

    launch_allowed_app("steam", settings)
    return False, (
        f"I opened Steam, but I do not know the App ID for '{requested}' yet. "
        "Add it in the Apps window under Steam Games, then ask again."
    )


def get_active_window_title() -> str:
    """Return the current foreground window title, or a friendly fallback."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            if buffer.value:
                return buffer.value.strip()
    except Exception:
        pass
    return "Unknown window"


def _strip_news_markup(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _first_feed_text(element: ET.Element, names: list[str]) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return _strip_news_markup(found.text)
    for child in list(element):
        local_name = child.tag.rsplit("}", 1)[-1].lower()
        if local_name in {name.lower().split(":")[-1] for name in names} and child.text:
            return _strip_news_markup(child.text)
    return ""


def _first_feed_link(element: ET.Element) -> str:
    rss_link = _first_feed_text(element, ["link"])
    if rss_link:
        return rss_link
    for child in list(element):
        if child.tag.rsplit("}", 1)[-1].lower() == "link":
            href = str(child.attrib.get("href", "")).strip()
            if href:
                return href
    return ""


def _parse_news_date(value: str) -> float:
    value = str(value or "").strip()
    if not value:
        return 0.0
    try:
        from email.utils import parsedate_to_datetime

        parsed = parsedate_to_datetime(value)
        return parsed.timestamp()
    except Exception:
        pass
    try:
        normalized = value.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(normalized).timestamp()
    except Exception:
        return 0.0


def fetch_news_items(category: str = "Top Stories", limit: int = 18) -> tuple[list[dict[str, str]], str]:
    feeds = DEFAULT_NEWS_FEEDS.get(category) or DEFAULT_NEWS_FEEDS["Top Stories"]
    items: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for feed_url in feeds:
        source_name = urlparse(feed_url).netloc.replace("www.", "") or "News"
        try:
            response = requests.get(
                feed_url,
                timeout=8,
                headers={"User-Agent": f"{APP_NAME}/1.0"},
            )
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
            continue

        entries = root.findall(".//item")
        if not entries:
            entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries:
            title = _first_feed_text(entry, ["title"])
            if not title:
                continue
            link = _first_feed_link(entry)
            description = _first_feed_text(entry, ["description", "summary", "content"])
            published = _first_feed_text(entry, ["pubDate", "published", "updated"])
            source = _first_feed_text(entry, ["source"]) or source_name
            key = re.sub(r"\W+", "", title.lower())
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": title,
                    "summary": description[:360],
                    "link": link,
                    "published": published,
                    "source": source,
                    "sort_time": str(_parse_news_date(published)),
                }
            )

    items.sort(key=lambda item: float(item.get("sort_time") or 0.0), reverse=True)
    for item in items:
        item.pop("sort_time", None)
    if items:
        return items[:limit], f"Loaded {min(len(items), limit)} headlines from {category}."
    if errors:
        return [], "News feeds could not be reached: " + "; ".join(errors[:2])
    return [], "No headlines were found. The newsroom appears to be taking a dramatic pause."


def fetch_video_news_items(channel: str = "Latest", limit: int = 18) -> tuple[list[dict[str, str]], str]:
    feeds = DEFAULT_VIDEO_NEWS_FEEDS.get(channel) or DEFAULT_VIDEO_NEWS_FEEDS["Latest"]
    items: list[dict[str, str]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for feed_url in feeds:
        try:
            response = requests.get(feed_url, timeout=8, headers={"User-Agent": f"{APP_NAME}/1.0"})
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as exc:
            errors.append(str(exc))
            continue

        feed_title = _first_feed_text(root, ["title"]) or "Video News"
        for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
            title = _first_feed_text(entry, ["title"])
            link = _first_feed_link(entry)
            if not title or not link or link in seen:
                continue
            seen.add(link)
            published = _first_feed_text(entry, ["published", "updated"])
            description = _first_feed_text(entry, ["description", "summary"])
            thumbnail = ""
            video_id = ""
            source = feed_title
            for child in entry.iter():
                local_name = child.tag.rsplit("}", 1)[-1].lower()
                if local_name == "thumbnail" and not thumbnail:
                    thumbnail = str(child.attrib.get("url", "")).strip()
                elif local_name == "videoid" and child.text:
                    video_id = child.text.strip()
                elif local_name == "name" and child.text and child.text.strip():
                    source = child.text.strip()
            if not thumbnail and video_id:
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            items.append(
                {
                    "type": "video",
                    "title": title,
                    "summary": description[:500],
                    "link": link,
                    "thumbnail": thumbnail,
                    "published": published,
                    "source": source,
                    "sort_time": str(_parse_news_date(published)),
                }
            )

    items.sort(key=lambda item: float(item.get("sort_time") or 0.0), reverse=True)
    for item in items:
        item.pop("sort_time", None)
    if items:
        return items[:limit], f"Loaded {min(len(items), limit)} videos from {channel}."
    if errors:
        return [], "Video feeds could not be reached: " + "; ".join(errors[:2])
    return [], "No video headlines were found."


class _ReadableArticleParser(HTMLParser):
    """Collect readable article paragraphs while ignoring page furniture."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._blocked_depth = 0
        self._paragraph_depth = 0
        self._buffer: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"}:
            self._blocked_depth += 1
        elif tag in {"p", "blockquote"} and self._blocked_depth == 0:
            self._paragraph_depth += 1
            if self._paragraph_depth == 1:
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"}:
            self._blocked_depth = max(0, self._blocked_depth - 1)
        elif tag in {"p", "blockquote"} and self._paragraph_depth:
            self._paragraph_depth -= 1
            if self._paragraph_depth == 0:
                paragraph = re.sub(r"\s+", " ", " ".join(self._buffer)).strip()
                if len(paragraph) >= 45 and paragraph not in self.paragraphs:
                    self.paragraphs.append(paragraph)

    def handle_data(self, data: str) -> None:
        if self._blocked_depth == 0 and self._paragraph_depth:
            cleaned = data.strip()
            if cleaned:
                self._buffer.append(cleaned)


def fetch_news_article(item: dict[str, str]) -> tuple[str, str]:
    """Fetch readable article text, falling back to the feed summary."""
    link = str(item.get("link", "")).strip()
    summary = str(item.get("summary", "")).strip()
    if not link:
        return summary, "This headline did not include a publisher link."
    try:
        response = requests.get(
            link,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 JARVIS/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
        parser = _ReadableArticleParser()
        parser.feed(response.text)
        paragraphs = parser.paragraphs
        text = "\n\n".join(paragraphs[:80]).strip()
        if len(text) >= 240:
            return text[:30000], f"Readable view loaded from {urlparse(link).netloc.replace('www.', '')}."
        if summary:
            return summary, "The publisher limited the readable preview. Showing the feed summary instead."
        return "", "The publisher did not provide readable article text. Use Publisher to view the original page."
    except Exception as exc:
        if summary:
            return summary, "The publisher page could not be read here. Showing the feed summary instead."
        return "", f"Article loading failed: {exc}"


def detect_music_apps() -> dict[str, bool]:
    """Detect common music apps from running processes and known install paths."""
    running = {proc.info["name"].lower() for proc in psutil.process_iter(["name"]) if proc.info.get("name")}
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    program_files = [Path(os.environ.get("PROGRAMFILES", "")), Path(os.environ.get("PROGRAMFILES(X86)", ""))]

    spotify_paths = [
        local_app_data / "Microsoft" / "WindowsApps" / "Spotify.exe",
        local_app_data / "Spotify" / "Spotify.exe",
    ]
    apple_paths = [folder / "Apple Music" / "AppleMusic.exe" for folder in program_files]
    apple_paths.append(local_app_data / "Microsoft" / "WindowsApps" / "AppleMusic.exe")
    itunes_paths = [folder / "iTunes" / "iTunes.exe" for folder in program_files]

    return {
        "spotify": "spotify.exe" in running or any(path.exists() for path in spotify_paths),
        "apple_music": (
            "applemusic.exe" in running
            or "itunes.exe" in running
            or any(path.exists() for path in apple_paths + itunes_paths)
        ),
        "youtube_music": True,
    }


def pick_playlist_for_window(window_title: str, settings: dict[str, Any] | None = None) -> dict[str, str]:
    title = window_title.lower()
    category = "general"
    if any(term in title for term in ["visual studio code", "vscode", "pycharm", "cursor"]):
        category = "coding"
    elif any(term in title for term in ["godot", "unity", "roblox studio", "unreal"]):
        category = "gamedev"
    elif any(term in title for term in ["chrome", "edge", "firefox", "browser"]):
        category = "browser"
    elif any(term in title for term in ["word", "google docs", "docs", "school", "onenote"]):
        category = "study"
    elif any(term in title for term in ["steam", "game", "minecraft", "valorant", "fortnite"]):
        category = "gaming"
    elif any(term in title for term in ["photoshop", "blender", "illustrator", "figma"]):
        category = "creative"

    playlist = dict(PLAYLISTS[category])
    playlist["category"] = category
    overrides = settings.get("playlist_overrides", {}) if isinstance(settings, dict) else {}
    override = overrides.get(category, {}) if isinstance(overrides, dict) else {}
    if isinstance(override, dict):
        for field in ["label", "url", "spotify_uri"]:
            value = str(override.get(field, "")).strip()
            if value:
                playlist[field] = value
    return playlist


def play_playlist(playlist: dict[str, str], preferred_app: str = "spotify") -> str:
    apps = detect_music_apps()

    if preferred_app == "spotify" and apps.get("spotify") and playlist.get("spotify_uri"):
        webbrowser.open(playlist["spotify_uri"])
        return "Spotify"

    if preferred_app in {"apple_music", "apple music"} and apps.get("apple_music"):
        webbrowser.open(playlist["url"])
        return "Apple Music/browser fallback"

    webbrowser.open(playlist["url"])
    return "browser"


def list_input_devices() -> list[dict[str, Any]]:
    if sd is None:
        return []
    devices = []
    try:
        for index, device in enumerate(sd.query_devices()):
            channels = int(device.get("max_input_channels", 0))
            if channels <= 0:
                continue
            devices.append(
                {
                    "index": index,
                    "name": str(device.get("name", "Unknown microphone")),
                    "channels": channels,
                    "hostapi": int(device.get("hostapi", -1)),
                    "sample_rate": int(float(device.get("default_samplerate", 44100))),
                }
            )
    except Exception:
        return []
    return devices


def get_input_device_label(device_index: int | None = None) -> str:
    if sd is None:
        return "No sounddevice backend"
    try:
        if device_index is None:
            info = sd.query_devices(kind="input")
            try:
                default_index = sd.default.device[0]
            except Exception:
                default_index = sd.default.device
            return f"{default_index}: {info.get('name', 'Default microphone')}"
        info = sd.query_devices(device_index)
        return f"{device_index}: {info.get('name', 'Selected microphone')}"
    except Exception:
        return "Unknown microphone"


def measure_microphone_level(device_index: int | None = None, seconds: float = 2.0) -> dict[str, Any]:
    if sd is None:
        raise RuntimeError("sounddevice is not installed")
    if np is None:
        raise RuntimeError("NumPy is not installed, and sounddevice needs it for voice recording")

    device_info = sd.query_devices(device_index, kind="input") if device_index is not None else sd.query_devices(kind="input")
    sample_rate = int(float(device_info.get("default_samplerate", 44100)))
    device_name = str(device_info.get("name", "Unknown microphone"))
    frames = max(1, int(seconds * sample_rate))
    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16", device=device_index)
    sd.wait()

    audio_array = np.asarray(recording, dtype=np.int16).reshape(-1)
    if not audio_array.size:
        peak = 0
        rms = 0
    else:
        peak = int(np.max(np.abs(audio_array)))
        rms = int(np.sqrt(np.mean(audio_array.astype(np.float32) ** 2)))
    return {
        "device_index": device_index,
        "device_name": device_name,
        "sample_rate": sample_rate,
        "peak": peak,
        "rms": rms,
    }


def clean_voice_audio(audio_array: Any, sample_rate: int) -> tuple[Any, dict[str, int]]:
    if np is None:
        return audio_array, {"raw_peak": 0, "clean_peak": 0, "raw_rms": 0, "clean_rms": 0}

    samples = np.asarray(audio_array, dtype=np.int16).reshape(-1)
    if not samples.size:
        return samples, {"raw_peak": 0, "clean_peak": 0, "raw_rms": 0, "clean_rms": 0}

    raw_peak = int(np.max(np.abs(samples)))
    raw_rms = int(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
    work = samples.astype(np.float32)
    work -= float(np.mean(work))

    abs_work = np.abs(work)
    threshold = max(180.0, min(2500.0, raw_rms * 1.8))
    spoken = np.flatnonzero(abs_work > threshold)
    if spoken.size:
        padding = int(sample_rate * 0.35)
        start = max(0, int(spoken[0]) - padding)
        end = min(work.size, int(spoken[-1]) + padding)
        if end > start:
            work = work[start:end]

    clean_peak_before_gain = float(np.max(np.abs(work))) if work.size else 0.0
    if clean_peak_before_gain > 0:
        target_peak = 14000.0
        gain = min(16.0, target_peak / clean_peak_before_gain)
        if gain > 1.0:
            work *= gain

    cleaned = np.clip(work, -32768, 32767).astype(np.int16)
    clean_peak = int(np.max(np.abs(cleaned))) if cleaned.size else 0
    clean_rms = int(np.sqrt(np.mean(cleaned.astype(np.float32) ** 2))) if cleaned.size else 0
    return cleaned, {
        "raw_peak": raw_peak,
        "clean_peak": clean_peak,
        "raw_rms": raw_rms,
        "clean_rms": clean_rms,
    }


def audio_data_to_wav_bytes(audio: sr.AudioData, target_rate: int = 16000) -> bytes:
    raw_data = audio.get_raw_data(convert_rate=target_rate, convert_width=2)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(target_rate)
        wav_file.writeframes(raw_data)
    return buffer.getvalue()


def capture_screen_png(max_width: int = 1600) -> tuple[bytes, tuple[int, int]]:
    image: Image.Image | None = None
    last_error: Exception | None = None
    try:
        image = ImageGrab.grab(all_screens=True)
    except Exception as exc:
        last_error = exc

    if image is None and mss is not None:
        try:
            with mss.mss() as screen_capture:
                monitor = screen_capture.monitors[0]
                shot = screen_capture.grab(monitor)
                image = Image.frombytes("RGB", shot.size, shot.rgb)
        except Exception as exc:
            last_error = exc

    if image is None:
        raise RuntimeError(f"Screen capture failed: {last_error}")

    original_size = image.size
    if image.width > max_width:
        ratio = max_width / float(image.width)
        resized = (max_width, max(1, int(image.height * ratio)))
        image = image.resize(resized, Image.Resampling.LANCZOS)
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), original_size


AGENT_SYSTEM_PROMPT = """
You are the tool-planning layer for JARVIS. Choose exactly one approved tool call
at a time, or return a final answer when the task is complete. You may not invent
tools, run terminal commands, delete files without confirmation, send messages,
buy things, change passwords, or enter private/private-looking information.
Clearing the Recycle Bin must use empty_recycle_bin and requires confirmation.

Return only compact JSON. No markdown. No commentary outside JSON.

Tool call schema:
{"action":"tool_name","args":{},"risk":"safe|medium|high","reason":"short reason"}

Final answer schema:
{"action":"final","args":{"summary":"what was done or why no tool is needed"},"risk":"safe","reason":"task complete"}

Use current window context. Ask for a screenshot with take_screenshot or analyze_screen
only if screen state matters. Prefer simple safe tools. Use ask_confirmation for
ambiguous or risky work.
""".strip()


def safe_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, flags=re.I):
        url = f"https://{url}"
    return url


def normalize_travel_mode(mode: str) -> str:
    mode = str(mode or "driving").lower().strip()
    aliases = {
        "drive": "driving",
        "car": "driving",
        "walk": "walking",
        "bike": "bicycling",
        "bicycle": "bicycling",
        "cycling": "bicycling",
        "transit": "transit",
        "bus": "transit",
        "train": "transit",
    }
    return aliases.get(mode, mode if mode in {"driving", "walking", "bicycling", "transit"} else "driving")


def maps_directions_url(origin: str, destination: str, mode: str = "driving") -> str:
    origin_q = requests.utils.quote(origin)
    destination_q = requests.utils.quote(destination)
    mode_q = requests.utils.quote(normalize_travel_mode(mode))
    return f"https://www.google.com/maps/dir/?api=1&origin={origin_q}&destination={destination_q}&travelmode={mode_q}"


def looks_like_coordinates(value: str) -> bool:
    return bool(re.match(r"^\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*$", str(value or "")))


def split_coordinates(value: str) -> tuple[str, str] | None:
    if not looks_like_coordinates(value):
        return None
    left, right = str(value).split(",", 1)
    return left.strip(), right.strip()


def reverse_geocode_coordinates(lat: Any, lon: Any) -> tuple[bool, str, str]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key or lat is None or lon is None:
        return False, "", "GOOGLE_MAPS_API_KEY is not loaded."
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"latlng": f"{lat},{lon}", "key": api_key},
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
        status = str(data.get("status", "UNKNOWN"))
        if status == "OK":
            results = data.get("results") or []
            if results:
                address = str(results[0].get("formatted_address") or "").strip()
                if address:
                    return True, address, "Reverse geocoding succeeded."
        error_message = str(data.get("error_message") or status)
        return False, "", f"Google Geocoding returned {error_message}."
    except Exception as exc:
        return False, "", f"Google Geocoding request failed: {exc}"


def reverse_geocode_coordinate_string(value: str) -> tuple[bool, str, str]:
    coords = split_coordinates(value)
    if coords is None:
        return False, "", "Location is not coordinates."
    return reverse_geocode_coordinates(coords[0], coords[1])


def lookup_ip_location() -> tuple[bool, str, str]:
    try:
        response = requests.get("https://ipapi.co/json/", timeout=4)
        response.raise_for_status()
        data = response.json()
        city = str(data.get("city") or "").strip()
        region = str(data.get("region") or "").strip()
        country = str(data.get("country_name") or "").strip()
        lat = data.get("latitude")
        lon = data.get("longitude")
        label_parts = [part for part in [city, region, country] if part]
        label = ", ".join(label_parts) if label_parts else "Approximate IP location"
        geocode_ok, formatted_address, geocode_status = reverse_geocode_coordinates(lat, lon)
        if geocode_ok and formatted_address:
            coordinates = f"{lat},{lon}" if lat is not None and lon is not None else ""
            suffix = f" (approximate, coordinates {coordinates})" if coordinates else " (approximate)"
            return True, formatted_address, f"{formatted_address}{suffix}"
        if label_parts:
            coordinates = f" Coordinates: {lat},{lon}." if lat is not None and lon is not None else ""
            geocode_note = f" {geocode_status}" if lat is not None and lon is not None else ""
            return True, label, f"{label} (approximate).{coordinates}{geocode_note}"
        if lat is not None and lon is not None:
            return True, label, f"{label} (approximate). Coordinates: {lat},{lon}. {geocode_status}"
    except Exception as exc:
        return False, "", f"IP location lookup failed: {exc}"
    return False, "", "IP location lookup did not return a usable location."


def get_configured_location(settings: dict[str, Any]) -> tuple[bool, str, str]:
    """Return (success, location, message). Location lookup happens only on demand."""
    manual = str(settings.get("manual_location", "")).strip()
    if manual:
        if looks_like_coordinates(manual):
            geocode_ok, address, geocode_status = reverse_geocode_coordinate_string(manual)
            if geocode_ok and address:
                settings["startup_location_coordinates"] = manual
                settings["manual_location"] = address
                settings["manual_location_label"] = "Reverse geocoded location"
                settings["location_provider"] = "manual"
                settings["location_enabled"] = True
                save_settings(settings)
                return True, address, f"Reverse geocoded location: {address}"
            if settings.get("auto_update_location_on_startup", False):
                success, message = auto_update_startup_location(settings)
                if success:
                    return True, str(settings.get("manual_location", "")).strip(), message
            return False, "", geocode_status
        label = str(settings.get("manual_location_label", "Saved location")).strip() or "Saved location"
        return True, manual, f"{label}: {manual}"

    if settings.get("auto_update_location_on_startup", False):
        success, message = auto_update_startup_location(settings)
        if success:
            return True, str(settings.get("manual_location", "")).strip(), message

    if not settings.get("location_enabled", False):
        return False, "", "Location is not configured. Say `set my location to ...` or enable approximate IP location in settings."

    provider = str(settings.get("location_provider", "manual")).lower().strip()
    if provider != "ip" or not settings.get("allow_ip_location_lookup", False):
        return False, "", "Approximate IP location is disabled. Sensible, if slightly inconvenient."

    return lookup_ip_location()


def auto_update_startup_location(settings: dict[str, Any]) -> tuple[bool, str]:
    if not settings.get("auto_update_location_on_startup", False):
        return False, "Startup location refresh is off."
    provider = str(settings.get("startup_location_provider", "ip")).lower().strip()
    if provider != "ip":
        return False, f"Startup location provider is not supported: {provider}"
    success, location, message = lookup_ip_location()
    if not success:
        return False, message
    settings["location_enabled"] = True
    settings["location_provider"] = "manual"
    settings["manual_location"] = location
    settings["manual_location_label"] = "Auto startup location"
    if "Coordinates:" in message:
        settings["startup_location_coordinates"] = message.split("Coordinates:", 1)[1].strip().rstrip(".")
    settings["allow_ip_location_lookup"] = True
    save_settings(settings)
    return True, f"Startup location set to {message}."


def get_maps_eta(origin: str, destination: str, mode: str = "driving") -> tuple[bool, str]:
    ok, info = get_maps_route_info(origin, destination, mode)
    if ok:
        return True, f"Estimated travel time is {info['duration']} for about {info['distance']}."
    return False, str(info.get("error", "Maps ETA failed."))


def resolve_nearby_place(origin: str, query: str) -> tuple[bool, dict[str, str]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return False, {"error": "No Google Maps API key configured for place search."}
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={
                "query": query,
                "location": origin if looks_like_coordinates(origin) else "",
                "radius": 50000,
                "key": api_key,
            },
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
        status = str(data.get("status", "UNKNOWN"))
        if status not in {"OK", "ZERO_RESULTS"}:
            return False, {"error": f"Places lookup failed: {data.get('error_message') or status}"}
        results = data.get("results") or []
        if not results:
            return False, {"error": f"No nearby place found for {query}."}
        place = results[0]
        geometry = place.get("geometry", {}).get("location", {})
        lat = geometry.get("lat")
        lng = geometry.get("lng")
        if lat is None or lng is None:
            return False, {"error": f"Places lookup found {query}, but no coordinates were returned."}
        name = str(place.get("name") or query).strip()
        address = str(place.get("formatted_address") or "").strip()
        return True, {
            "name": name,
            "address": address,
            "destination": f"{lat},{lng}",
            "maps_label": f"{name}, {address}" if address else name,
        }
    except Exception as exc:
        return False, {"error": f"Places lookup failed: {exc}"}


def get_maps_route_info(origin: str, destination: str, mode: str = "driving") -> tuple[bool, dict[str, str]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return False, {"error": "No Google Maps API key configured for exact ETA."}
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/distancematrix/json",
            params={
                "origins": origin,
                "destinations": destination,
                "mode": normalize_travel_mode(mode),
                "departure_time": "now",
                "key": api_key,
            },
            timeout=6,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "OK":
            return False, {"error": f"Maps ETA failed: {data.get('status', 'unknown error')}"}
        row = (data.get("rows") or [{}])[0]
        element = (row.get("elements") or [{}])[0]
        if element.get("status") != "OK":
            return False, {"error": f"Maps ETA failed: {element.get('status', 'unknown route status')}"}
        distance = element.get("distance", {}).get("text", "unknown distance")
        duration = element.get("duration_in_traffic", element.get("duration", {})).get("text", "unknown time")
        return True, {
            "origin": str(origin),
            "destination": str(destination),
            "distance": str(distance),
            "duration": str(duration),
            "mode": normalize_travel_mode(mode),
        }
    except Exception as exc:
        return False, {"error": f"Maps ETA failed: {exc}"}


def _route_seconds(route: dict[str, Any]) -> int:
    legs = route.get("legs") or []
    total = 0
    for leg in legs:
        duration = leg.get("duration_in_traffic") or leg.get("duration") or {}
        total += int(duration.get("value") or 0)
    return total


def get_fastest_directions_route_info(origin: str, destination: str, mode: str = "driving") -> tuple[bool, dict[str, str]]:
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not api_key:
        return False, {"error": "No Google Maps API key configured for fastest-route lookup."}
    mode = normalize_travel_mode(mode)
    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params={
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "alternatives": "true",
                "departure_time": "now",
                "traffic_model": "best_guess",
                "key": api_key,
            },
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        status = str(data.get("status", "UNKNOWN"))
        if status != "OK":
            return False, {"error": f"Directions lookup failed: {data.get('error_message') or status}"}
        routes = data.get("routes") or []
        if not routes:
            return False, {"error": "Directions lookup returned no routes."}
        best_route = min(routes, key=_route_seconds)
        legs = best_route.get("legs") or []
        if not legs:
            return False, {"error": "Directions lookup returned a route with no legs."}
        distance_meters = sum(int((leg.get("distance") or {}).get("value") or 0) for leg in legs)
        duration_seconds = _route_seconds(best_route)
        distance_text = legs[0].get("distance", {}).get("text", "unknown distance") if len(legs) == 1 else f"{distance_meters / 1609.344:.1f} mi"
        if duration_seconds:
            minutes = max(1, round(duration_seconds / 60))
            duration_text = f"{minutes} min" if minutes < 60 else f"{minutes // 60} hr {minutes % 60} min".strip()
        else:
            duration_text = legs[0].get("duration", {}).get("text", "unknown time")
        summary = str(best_route.get("summary") or "fastest available route").strip()
        return True, {
            "origin": str(origin),
            "destination": str(destination),
            "distance": str(distance_text),
            "duration": str(duration_text),
            "mode": mode,
            "route_summary": summary,
            "route_count": str(len(routes)),
        }
    except Exception as exc:
        return False, {"error": f"Directions lookup failed: {exc}"}


def get_nearby_route_info(origin: str, query: str, mode: str = "driving") -> tuple[bool, dict[str, str]]:
    place_ok, place = resolve_nearby_place(origin, query)
    if not place_ok:
        return False, place
    route_ok, route = get_fastest_directions_route_info(origin, place["destination"], mode)
    if not route_ok:
        matrix_ok, matrix_route = get_maps_route_info(origin, place["destination"], mode)
        if matrix_ok:
            matrix_route["route_summary"] = "best route from Distance Matrix"
            route_ok, route = True, matrix_route
    if not route_ok:
        route["place_name"] = place.get("name", query)
        route["place_address"] = place.get("address", "")
        route["resolved_destination"] = place.get("destination", query)
        route["maps_label"] = place.get("maps_label", query)
        return False, route
    route["place_name"] = place.get("name", query)
    route["place_address"] = place.get("address", "")
    route["resolved_destination"] = place.get("destination", query)
    route["maps_label"] = place.get("maps_label", query)
    return True, route


class ToolRegistry:
    """Approved local tools the agent may choose from. No arbitrary shell access."""

    def __init__(self, assistant: "JarvisAssistant") -> None:
        self.assistant = assistant
        self.tools: dict[str, dict[str, Any]] = {}
        self._register_tools()

    def _register(self, name: str, risk: str, description: str, handler: Callable[[dict[str, Any]], str]) -> None:
        self.tools[name] = {
            "name": name,
            "risk": risk,
            "description": description,
            "handler": handler,
        }

    def _register_tools(self) -> None:
        self._register("take_screenshot", "safe", "Save a screenshot to the screenshots folder.", self._take_screenshot)
        self._register("analyze_screen", "safe", "Analyze the current screen with Gemini vision.", self._analyze_screen)
        self._register("get_active_window", "safe", "Return the active window title.", self._get_active_window)
        self._register("click", "safe", "Left-click at screen coordinates.", self._click)
        self._register("double_click", "safe", "Double-click at screen coordinates.", self._double_click)
        self._register("right_click", "safe", "Right-click at screen coordinates.", self._right_click)
        self._register("type_text", "medium", "Type text into the focused field.", self._type_text)
        self._register("press_key", "safe", "Press a single approved key.", self._press_key)
        self._register("hotkey", "medium", "Press an approved hotkey combination.", self._hotkey)
        self._register("scroll", "safe", "Scroll up or down.", self._scroll)
        self._register("open_app", "medium", "Open a whitelisted app.", self._open_app)
        self._register("switch_window", "safe", "Switch to a visible window by title.", self._switch_window)
        self._register("open_url", "medium", "Open a URL in the default browser.", self._open_url)
        self._register("search_web", "safe", "Search the web in the default browser.", self._search_web)
        self._register("get_location", "safe", "Return the user's configured or explicitly enabled approximate location.", self._get_location)
        self._register("open_directions", "medium", "Open Google Maps directions to a destination.", self._open_directions)
        self._register("get_eta", "safe", "Get an ETA if a Google Maps API key is configured, otherwise explain the fallback.", self._get_eta)
        self._register("get_coding_workspace", "safe", "Describe the selected coding workspace and approved runners.", self._get_coding_workspace)
        self._register("search_code", "safe", "Search filenames and source contents in the selected coding workspace.", self._search_code)
        self._register("read_code_file", "safe", "Read a UTF-8 source file inside the selected coding workspace.", self._read_code_file)
        self._register("diagnose_code_project", "safe", "Run local syntax and merge-conflict diagnostics on the coding workspace.", self._diagnose_code_project)
        self._register("run_code_check", "high", "Run one discovered, fixed, approved test or build check. Project code may execute.", self._run_code_check)
        self._register("list_folder", "safe", "List files in a folder.", self._list_folder)
        self._register("open_file", "medium", "Open an existing file with its default app.", self._open_file)
        self._register("create_folder", "medium", "Create a folder.", self._create_folder)
        self._register("move_file", "high", "Move a file to another folder. Confirmation required.", self._move_file)
        self._register("delete_file", "high", "Delete a file. Confirmation required.", self._delete_file)
        self._register("empty_recycle_bin", "high", "Empty the Windows Recycle Bin. Confirmation required.", self._empty_recycle_bin)
        self._register("play_music", "medium", "Play or search for music using the existing music system.", self._play_music)
        self._register("ask_confirmation", "safe", "Ask the user to confirm before continuing.", self._ask_confirmation)
        self._register("cancel_task", "safe", "Cancel the current task.", self._cancel_task)

    def descriptions(self) -> list[dict[str, str]]:
        return [
            {"name": name, "risk": str(tool["risk"]), "description": str(tool["description"])}
            for name, tool in self.tools.items()
        ]

    def validate(self, call: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
        if not isinstance(call, dict):
            return False, "Tool call was not a JSON object.", None
        action = str(call.get("action", "")).strip()
        if action == "final":
            return True, "", None
        tool = self.tools.get(action)
        if tool is None:
            return False, f"Unapproved tool: {action}", None
        args = call.get("args", {})
        if not isinstance(args, dict):
            return False, "Tool args must be an object.", None
        declared_risk = str(call.get("risk", tool["risk"])).lower()
        if declared_risk not in {"safe", "medium", "high"}:
            return False, f"Invalid risk level: {declared_risk}", None
        return True, "", tool

    def requires_confirmation(self, call: dict[str, Any], tool: dict[str, Any]) -> bool:
        tool_risk = str(tool["risk"])
        declared_risk = str(call.get("risk", tool_risk)).lower()
        effective = "high" if "high" in {tool_risk, declared_risk} else ("medium" if "medium" in {tool_risk, declared_risk} else "safe")
        if self.assistant.current_mode.lower() == "safe" and str(call.get("action", "")) in {
            "click",
            "double_click",
            "right_click",
            "type_text",
            "hotkey",
            "press_key",
            "move_file",
            "delete_file",
            "empty_recycle_bin",
            "run_code_check",
        }:
            return True

        permission_mode = str(self.assistant.settings.get("agent_permission_mode", "Ask for approval"))
        if permission_mode not in PERMISSION_MODES:
            permission_mode = "Ask for approval"
        if permission_mode == "Full access":
            return False
        if permission_mode == "Approve for me":
            return effective == "high"
        return effective in {"medium", "high"}

    def execute(self, call: dict[str, Any]) -> str:
        ok, error, tool = self.validate(call)
        if not ok or tool is None:
            message = f"Tool rejected: {error}"
            self.assistant.record_action(str(call.get("action", "unknown")), call.get("args", {}), str(call.get("risk", "unknown")), False, message)
            return message
        args = call.get("args", {})
        self.assistant.last_action = str(call.get("action", "tool"))
        self.assistant.last_risk = str(call.get("risk", tool["risk"]))
        try:
            message = str(tool["handler"](args))
            success = self.assistant.action_message_indicates_success(message)
            self.assistant.record_action(str(call.get("action", "tool")), args, self.assistant.last_risk, success, message)
            return message
        except Exception as exc:
            message = f"Tool failed: {exc}"
            self.assistant.record_action(str(call.get("action", "tool")), args, self.assistant.last_risk, False, message)
            return message

    def _take_screenshot(self, _args: dict[str, Any]) -> str:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        filename = SCREENSHOTS_DIR / f"agent_screenshot_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        ImageGrab.grab().save(filename)
        return f"Screenshot saved: {filename}"

    def _analyze_screen(self, args: dict[str, Any]) -> str:
        prompt = str(args.get("question") or args.get("prompt") or "Analyze the current screen.")
        return self.assistant.analyze_screen_with_gemini(prompt)

    def _get_active_window(self, _args: dict[str, Any]) -> str:
        return f"Active window: {get_active_window_title()}"

    def _point(self, args: dict[str, Any]) -> tuple[int, int]:
        return clamp_screen_point(int(args.get("x", 0)), int(args.get("y", 0)))

    def _click(self, args: dict[str, Any]) -> str:
        x, y = self._point(args)
        click_mouse(x, y)
        return f"Clicked at {x}, {y}."

    def _double_click(self, args: dict[str, Any]) -> str:
        x, y = self._point(args)
        click_mouse(x, y, double=True)
        return f"Double-clicked at {x}, {y}."

    def _right_click(self, args: dict[str, Any]) -> str:
        x, y = self._point(args)
        click_mouse(x, y, button="right")
        return f"Right-clicked at {x}, {y}."

    def _type_text(self, args: dict[str, Any]) -> str:
        text = str(args.get("text", ""))
        if not text:
            return "No text supplied."
        if not set_windows_clipboard_text(text):
            return "Could not set clipboard for typing."
        if paste_windows_clipboard():
            return f"Typed {len(text)} characters."
        return "Clipboard was set, but paste failed."

    def _press_key(self, args: dict[str, Any]) -> str:
        key = str(args.get("key", "")).lower().strip()
        if send_safe_key(key):
            return f"Pressed {key}."
        return f"Key not approved or unavailable: {key}"

    def _hotkey(self, args: dict[str, Any]) -> str:
        keys = args.get("keys", [])
        if isinstance(keys, str):
            parts = re.split(r"[+, ]+", keys)
        elif isinstance(keys, list):
            parts = [str(key) for key in keys]
        else:
            return "Hotkey keys must be a string or list."
        normalized = [part.lower().strip() for part in parts if str(part).strip()]
        allowed = {
            "ctrl",
            "control",
            "shift",
            "alt",
            "win",
            "windows",
            "tab",
            "enter",
            "escape",
            "esc",
            "space",
            "f",
            "a",
            "c",
            "v",
            "x",
            "z",
            "y",
            "s",
            "n",
            "t",
            "w",
            "r",
        }
        if not normalized or any(key not in allowed for key in normalized):
            return f"Hotkey rejected: {'+'.join(normalized)}"
        combo = "+".join("ctrl" if key == "control" else ("win" if key == "windows" else key) for key in normalized)
        if keyboard is not None:
            keyboard.press_and_release(combo)
            return f"Pressed hotkey {combo}."
        if ensure_ui_automation_available() and win_keyboard is not None:
            token_map = {"ctrl": "^", "shift": "+", "alt": "%"}
            if all(key in token_map or len(key) == 1 for key in normalized):
                token = "".join(token_map.get(key, key) for key in normalized)
                win_keyboard.send_keys(token)
                return f"Pressed hotkey {combo}."
        return "Hotkey support is unavailable."

    def _scroll(self, args: dict[str, Any]) -> str:
        direction = str(args.get("direction", "down")).lower()
        amount = int(args.get("amount", 5) or 5)
        if direction not in {"up", "down"}:
            return "Scroll direction must be up or down."
        scroll_mouse(direction, amount)
        return f"Scrolled {direction}."

    def _open_app(self, args: dict[str, Any]) -> str:
        name = str(args.get("app_name") or args.get("name") or "")
        launched, message = launch_allowed_app(name, self.assistant.settings)
        return message if launched else f"Could not open app: {message}"

    def _switch_window(self, args: dict[str, Any]) -> str:
        query = str(args.get("title") or args.get("query") or "")
        title = focus_window_by_title(query)
        return f"Switched to: {title}" if title else f"No visible window matched '{query}'."

    def _open_url(self, args: dict[str, Any]) -> str:
        url = safe_url(str(args.get("url", "")))
        if not url:
            return "No URL supplied."
        webbrowser.open(url)
        return f"Opened URL: {url}"

    def _search_web(self, args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return "No search query supplied."
        webbrowser.open(f"https://www.google.com/search?q={requests.utils.quote(query)}")
        return f"Searched the web for: {query}"

    def _get_location(self, _args: dict[str, Any]) -> str:
        success, location, message = get_configured_location(self.assistant.settings)
        return f"Current location: {location}." if success else f"Location unavailable: {message}"

    def _open_directions(self, args: dict[str, Any]) -> str:
        destination = str(args.get("destination", "")).strip()
        origin = str(args.get("origin", "")).strip()
        mode = normalize_travel_mode(str(args.get("mode") or self.assistant.settings.get("directions_travel_mode", "driving")))
        if not destination:
            return "No destination supplied."
        if not origin:
            ok, origin, message = get_configured_location(self.assistant.settings)
            if not ok:
                return f"I need a starting location first. {message}"
        webbrowser.open(maps_directions_url(origin, destination, mode))
        return f"Opened {mode} directions from {origin} to {destination}."

    def _get_eta(self, args: dict[str, Any]) -> str:
        destination = str(args.get("destination", "")).strip()
        origin = str(args.get("origin", "")).strip()
        mode = normalize_travel_mode(str(args.get("mode") or self.assistant.settings.get("directions_travel_mode", "driving")))
        if not destination:
            return "No destination supplied."
        if not origin:
            ok, origin, message = get_configured_location(self.assistant.settings)
            if not ok:
                return f"I need a starting location first. {message}"
        ok, eta = get_maps_eta(origin, destination, mode)
        if ok:
            return eta
        return f"{eta} I can still open Google Maps directions for live ETA."

    def _coding_root(self) -> Path | None:
        value = str(self.assistant.settings.get("coding_workspace_folder", "")).strip()
        return normalize_watch_folder(value) if value else None

    def _get_coding_workspace(self, _args: dict[str, Any]) -> str:
        root = self._coding_root()
        if root is None:
            return "No coding workspace is selected. Open the Code panel and choose a project first."
        runners = approved_code_runners(root)
        runner_text = ", ".join(f"{item['id']} ({item['risk']})" for item in runners) or "none"
        return f"Coding workspace: {root}\nProject type: {detect_coding_project_type(root)}\nApproved runners: {runner_text}"

    def _search_code(self, args: dict[str, Any]) -> str:
        root = self._coding_root()
        if root is None:
            return "No coding workspace is selected."
        query = str(args.get("query", "")).strip()
        if not query:
            return "A code search query is required."
        files = coding_workspace_files(root, query=query, limit=60)
        if not files:
            return f"No coding workspace files matched '{query}'."
        return "Code search matches:\n" + "\n".join(f"- {path.relative_to(root)}" for path in files)

    def _read_code_file(self, args: dict[str, Any]) -> str:
        root = self._coding_root()
        if root is None:
            return "No coding workspace is selected."
        relative = str(args.get("path") or args.get("file") or "").strip().strip('"')
        if not relative:
            return "A workspace-relative file path is required."
        path = safe_coding_workspace_file(root, root / relative)
        if path is None:
            return "The requested file is missing, too large, or outside the coding workspace."
        if not is_agent_readable_code_file(path):
            return "That file type is blocked from AI tool context because it may contain credentials or private keys."
        ok, text = read_coding_file(path, max_chars=24000)
        if not ok:
            return text
        return f"FILE: {path.relative_to(root)}\n\n{redact_code_secrets(text)}"

    def _diagnose_code_project(self, _args: dict[str, Any]) -> str:
        root = self._coding_root()
        if root is None:
            return "No coding workspace is selected."
        limit = int(self.assistant.settings.get("coding_workspace_max_files", 800))
        return format_coding_diagnostics(diagnose_coding_workspace(root, limit=limit))

    def _run_code_check(self, args: dict[str, Any]) -> str:
        root = self._coding_root()
        if root is None:
            return "No coding workspace is selected."
        runner_id = str(args.get("runner_id") or args.get("runner") or "").strip()
        result = run_approved_code_runner(root, runner_id, timeout_seconds=120)
        output = str(result.get("output", ""))
        if len(output) > 24000:
            output = "[Earlier output truncated]\n" + output[-24000:]
        status_word = "passed" if result.get("ok") else "failed"
        return (
            f"Runner: {result.get('label', runner_id)} {status_word}.\n"
            f"Result: {'PASS' if result.get('ok') else 'FAIL'}\n"
            f"Exit code: {result.get('returncode')}\n"
            f"Duration: {result.get('duration', 0)} seconds\n\n{output}"
        )
    def _resolve_path_arg(self, args: dict[str, Any], key: str = "path") -> Path:
        return Path(os.path.expandvars(os.path.expanduser(str(args.get(key, "")).strip().strip('"')))).resolve()

    def _list_folder(self, args: dict[str, Any]) -> str:
        path = self._resolve_path_arg(args)
        if not path.exists() or not path.is_dir():
            return f"Folder not found: {path}"
        items = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:40]
        if not items:
            return f"Folder is empty: {path}"
        lines = [f"Items in {path}:"]
        for item in items:
            lines.append(f"- {item.name}{'/' if item.is_dir() else ''}")
        return "\n".join(lines)

    def _open_file(self, args: dict[str, Any]) -> str:
        path = self._resolve_path_arg(args)
        if not path.exists() or not path.is_file():
            return f"File not found: {path}"
        _launch_path(path)
        return f"Opened file: {path}"

    def _create_folder(self, args: dict[str, Any]) -> str:
        path = self._resolve_path_arg(args)
        path.mkdir(parents=True, exist_ok=True)
        return f"Created folder: {path}"

    def _move_file(self, args: dict[str, Any]) -> str:
        source = self._resolve_path_arg(args, "source")
        destination = self._resolve_path_arg(args, "destination")
        if not source.exists() or not source.is_file():
            return f"Source file not found: {source}"
        if destination.exists() and destination.is_dir():
            destination = destination / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return f"Moved file from {source} to {destination}."

    def _delete_file(self, args: dict[str, Any]) -> str:
        path = self._resolve_path_arg(args)
        if not path.exists() or not path.is_file():
            return f"File not found: {path}"
        path.unlink()
        return f"Deleted file: {path}"

    def _empty_recycle_bin(self, _args: dict[str, Any]) -> str:
        success, message = clear_recycle_bin()
        return message if success else f"I could not clear the Recycle Bin. {message}"

    def _play_music(self, args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            return self.assistant._music_you_pick(re.match(r".*", ""), "play music, you pick")  # type: ignore[arg-type]
        return self.assistant._play_apple_music_query(query)

    def _ask_confirmation(self, args: dict[str, Any]) -> str:
        question = str(args.get("question") or "Please confirm this action.")
        self.assistant.pending_confirmation = {
            "action": "agent_message",
            "label": "agent confirmation",
            "message": question,
        }
        return f"{question} Say confirm to proceed or cancel to stop."

    def _cancel_task(self, args: dict[str, Any]) -> str:
        return str(args.get("reason") or "Task cancelled.")


class GeminiProxyModels:
    def __init__(self, client: "GeminiProxyClient") -> None:
        self.client = client

    def list(self) -> list[Any]:
        response = self.client.session.get(
            f"{self.client.base_url}/v1/models",
            headers=self.client.headers,
            timeout=12,
        )
        self.client.raise_for_status(response)
        models = response.json().get("models", [])
        return [
            SimpleNamespace(
                name=str(item.get("name", "")),
                supported_generation_methods=item.get("supportedGenerationMethods", ["generateContent"]),
            )
            for item in models
        ]

    def generate_content(self, model: str, contents: Any, config: Any | None = None) -> Any:
        payload: dict[str, Any] = {
            "model": str(model).removeprefix("models/"),
            "contents": self._normalize_contents(contents),
        }
        if config is not None:
            config_data = config.model_dump(exclude_none=True) if hasattr(config, "model_dump") else dict(config)
            system_instruction = config_data.get("system_instruction")
            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": str(system_instruction)}],
                }
            generation_config: dict[str, Any] = {}
            if config_data.get("response_mime_type"):
                generation_config["responseMimeType"] = str(config_data["response_mime_type"])
            if generation_config:
                payload["generationConfig"] = generation_config
        response = self.client.session.post(
            f"{self.client.base_url}/v1/generate",
            headers=self.client.headers,
            json=payload,
            timeout=90,
        )
        self.client.raise_for_status(response)
        data = response.json()
        text_parts: list[str] = []
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    text_parts.append(str(part["text"]))
        return SimpleNamespace(text="".join(text_parts), raw=data)

    def _normalize_contents(self, contents: Any) -> list[dict[str, Any]]:
        values = contents if isinstance(contents, list) else [contents]
        parts = [self._normalize_part(value) for value in values]
        return [{"role": "user", "parts": [part for part in parts if part]}]

    def _normalize_part(self, value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            return {"text": value}
        data = value.model_dump(exclude_none=True) if hasattr(value, "model_dump") else value
        if isinstance(data, dict):
            if data.get("text") is not None:
                return {"text": str(data["text"])}
            inline = data.get("inline_data") or data.get("inlineData")
            if isinstance(inline, dict):
                raw_data = inline.get("data", b"")
                if isinstance(raw_data, str):
                    encoded = raw_data
                else:
                    encoded = base64.b64encode(bytes(raw_data)).decode("ascii")
                return {
                    "inlineData": {
                        "mimeType": str(inline.get("mime_type") or inline.get("mimeType") or "application/octet-stream"),
                        "data": encoded,
                    }
                }
        raise TypeError(f"Unsupported Gemini proxy content type: {type(value).__name__}")


class GeminiProxyClient:
    def __init__(self, base_url: str, installation_id: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
            "X-JARVIS-Version": APP_VERSION,
            "X-JARVIS-Install": installation_id,
        }
        self.models = GeminiProxyModels(self)

    @staticmethod
    def raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return
        try:
            detail = response.json().get("error") or response.text
        except Exception:
            detail = response.text
        raise RuntimeError(f"Proxy returned HTTP {response.status_code}: {detail}")


class JarvisAssistant:
    def __init__(self) -> None:
        load_environment()
        self.settings = load_settings()
        if not str(self.settings.get("installation_id", "")).strip():
            self.settings["installation_id"] = str(uuid.uuid4())
            save_settings(self.settings)
        self.personality = load_personality()
        self.settings["ai_provider"] = os.getenv("AI_PROVIDER", self.settings.get("ai_provider", "gemini")).lower()
        self.current_mode = str(self.settings.get("assistant_mode", "Normal")).title()
        self.last_action = "Startup"
        self.last_risk = "safe"
        self.last_verified_action = "No verified actions yet"
        self.action_ledger: list[dict[str, Any]] = []
        self.openai_client: OpenAI | None = None
        self.gemini_client: Any | None = None
        self.available_gemini_models: list[str] = []
        self.gemini_model_status = "Gemini model auto-select has not run yet."
        self.memories = load_memories()
        self.history: list[dict[str, str]] = []
        self.max_history = 8
        self.pending_confirmation: dict[str, Any] | None = None
        self.pending_music_request: dict[str, Any] | None = None
        self.pending_music_device_request: dict[str, Any] | None = None
        self.pending_navigation_request: dict[str, Any] | None = None
        self.phone_queue = PhoneActionQueue(PHONE_QUEUE_PATH)
        self.command_handlers: list[tuple[re.Pattern[str], Callable[[re.Match[str], str], str]]] = []
        self.tool_registry = ToolRegistry(self)
        self._setup_ai_clients()
        self._setup_commands()

    def _setup_ai_clients(self) -> None:
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = OpenAI()
        proxy_url = os.getenv("JARVIS_AI_PROXY_URL", "").strip()
        if proxy_url:
            self.gemini_client = GeminiProxyClient(proxy_url, str(self.settings.get("installation_id", "unknown")))
        elif genai is not None and os.getenv("GEMINI_API_KEY"):
            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def refresh_gemini_model_selection(self) -> str:
        if genai is None or self.gemini_client is None:
            self.gemini_model_status = "Gemini is not configured, so model auto-select was skipped."
            return self.gemini_model_status

        if not self.settings.get("auto_select_gemini_model", True):
            current = self.settings.get("gemini_model", "gemini-2.5-flash")
            self.gemini_model_status = f"Gemini auto-select is off. Using {current}."
            return self.gemini_model_status

        try:
            models = self._list_available_gemini_models()
            self.available_gemini_models = models
            if not models:
                raise RuntimeError("No text-generation Gemini models were returned.")

            selected = models[0]
            fast_models = [model for model in models if "flash-lite" in model.lower()]
            if fast_models:
                self.settings["gemini_fast_model"] = fast_models[0]
            old_model = self.settings.get("gemini_model")
            self.settings["gemini_model"] = selected
            fallback_models = [model for model in models[1:] if model != selected]
            configured = self.settings.get("gemini_fallback_models", [])
            fallback_models.extend(str(model) for model in configured if model and model != selected)
            self.settings["gemini_fallback_models"] = list(dict.fromkeys(fallback_models))
            save_settings(self.settings)

            if selected == old_model:
                self.gemini_model_status = f"Gemini model ready: {selected}."
            else:
                self.gemini_model_status = f"Gemini model auto-selected: {selected}."
        except Exception as exc:
            self.available_gemini_models = []
            self.gemini_model_status = f"Gemini model auto-select failed. Using saved fallback list. ({exc})"
        return self.gemini_model_status

    def _list_available_gemini_models(self) -> list[str]:
        if self.gemini_client is None:
            return []

        raw_models = list(self.gemini_client.models.list())
        names: list[str] = []
        for model in raw_models:
            name = self._clean_gemini_model_name(getattr(model, "name", ""))
            if name and self._is_usable_gemini_text_model(model, name):
                names.append(name)
        return sorted(list(dict.fromkeys(names)), key=self._gemini_model_rank, reverse=True)

    def _clean_gemini_model_name(self, name: str) -> str:
        name = str(name or "").strip()
        return name.removeprefix("models/")

    def _is_usable_gemini_text_model(self, model: Any, name: str) -> bool:
        lowered = name.lower()
        blocked_terms = [
            "embedding",
            "imagen",
            "veo",
            "aqa",
            "tts",
            "image",
            "vision",
            "audio",
            "live",
            "preview",
            "experimental",
            "exp",
        ]
        if not lowered.startswith("gemini") or any(term in lowered for term in blocked_terms):
            return False

        supported = getattr(model, "supported_actions", None)
        if supported:
            return "generateContent" in supported or "generate_content" in supported
        methods = getattr(model, "supported_generation_methods", None)
        if methods:
            return "generateContent" in methods or "generate_content" in methods
        return "flash" in lowered or "pro" in lowered

    def _gemini_model_rank(self, model: str) -> tuple[int, int, int, int, int]:
        lowered = model.lower()
        version_match = re.search(r"gemini-(\d+)(?:\.(\d+))?", lowered)
        major = int(version_match.group(1)) if version_match else 0
        minor = int(version_match.group(2) or 0) if version_match else 0
        flash_score = 3 if "flash" in lowered else 1
        lite_score = -1 if "lite" in lowered else 0
        alias_score = -2 if "latest" in lowered else 0
        return major, minor, flash_score, lite_score, alias_score

    def _gemini_models_to_try(self) -> list[str]:
        models: list[str] = []
        if self.available_gemini_models:
            models.extend(self.available_gemini_models)
        models.append(str(self.settings.get("gemini_model", "gemini-2.5-flash")))
        models.extend(str(model) for model in self.settings.get("gemini_fallback_models", []) if model)
        models.extend(["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"])
        return list(dict.fromkeys(self._clean_gemini_model_name(model) for model in models if model))

    def _use_fast_chat_model(self, user_text: str) -> bool:
        if not self.settings.get("prefer_fast_model_for_simple_chat", True):
            return False
        text = user_text.strip().lower()
        if not text or len(text) > 240 or text.count("\n") > 1:
            return False
        complex_terms = (
            "analyze", "in detail", "compare", "research", "write me", "rewrite",
            "review", "critique", "code", "debug", "plan", "step by step",
            "summarize", "explain why", "deep dive",
        )
        return not any(term in text for term in complex_terms)

    def _gemini_chat_models_to_try(self, user_text: str) -> tuple[list[str], bool]:
        models = self._gemini_models_to_try()
        use_fast = self._use_fast_chat_model(user_text)
        if not use_fast:
            return models, False
        fast_model = self._clean_gemini_model_name(str(self.settings.get("gemini_fast_model", "")))
        if not fast_model:
            fast_model = next((model for model in models if "flash-lite" in model.lower()), "")
        if fast_model:
            models = [fast_model, *[model for model in models if model != fast_model]]
        return models, bool(fast_model)

    def _is_recoverable_gemini_error(self, exc: Exception) -> bool:
        message = str(exc).upper()
        recoverable_terms = [
            "429",
            "503",
            "RESOURCE_EXHAUSTED",
            "RATE_LIMIT",
            "QUOTA",
            "UNAVAILABLE",
            "MODEL_NOT_FOUND",
            "NOT FOUND",
            "NOT_FOUND",
            "PERMISSION_DENIED",
            "INVALID_ARGUMENT",
            "IS NOT FOUND",
            "NOT SUPPORTED",
            "UNSUPPORTED",
        ]
        return any(term in message for term in recoverable_terms)

    def _setup_commands(self) -> None:
        self.command_handlers = [
            (re.compile(r"\bwhat (am i working on|window is open)\b|\bcurrent window\b", re.I), self._active_window),
            (re.compile(r"\b(?:can you|could you|are you able to|capable of).*(?:apple music|music app).*(?:search|find|play|song|track)\b", re.I), self._request_apple_music_song),
            (re.compile(r"\b(?:open|launch|use)\s+apple music\s+(?:and\s+)?(?:search|find|play)(?:\s+for)?\s+(.+)", re.I | re.S), self._apple_music_search_command),
            (re.compile(r"\b(?:search|find)\s+(?:apple music|music app)\s+(?:for\s+)?(.+)", re.I | re.S), self._apple_music_search_command),
            (re.compile(r"\b(?:look at|see|analyze|scan|read)\s+(?:my\s+)?screen\b|\bwhat(?:'s| is) on (?:my\s+)?screen\b|\bwhat should i click\b|\bwhere should i click\b", re.I), self._look_at_screen),
            (re.compile(r"\b(?:agent tools|tool registry|list tools|what tools do you have)\b", re.I), self._list_agent_tools),
            (re.compile(r"\b(?:integration status|integrations status|list integrations|what integrations do you have|show integrations)\b", re.I), self._integrations_status),
            (re.compile(r"\b(?:action history|action ledger|recent actions|what did you do)\b", re.I), self._action_history),
            (re.compile(r"\b(?:(?:set|switch to|enter|enable|activate)\s+)?(coding|school|gaming|focus|safe|normal)\s+mode\b", re.I), self._set_mode),
            (re.compile(r"\b(?:what mode|current mode|mode status)\b", re.I), self._mode_status),
            (re.compile(r"\b(list|show)\s+(microphones|mics|input devices)\b", re.I), self._list_microphones),
            (re.compile(r"\b(?:use|select|set)\s+(?:microphone|mic|input device)\s+(\d+)\b", re.I), self._set_microphone),
            (re.compile(r"\b(?:test|check)\s+(?:microphone|mic)\b", re.I), self._test_microphone),
            (re.compile(r"\b(?:auto\s*(?:detect|select|choose)|find)\s+(?:microphone|mic)\b", re.I), self._auto_select_microphone),
            (re.compile(r"\b(?:music status|music settings|music diagnostics|audio status)\b", re.I), self._music_settings_status),
            (re.compile(r"\b(play|start).*(music|playlist).*(you pick|pick|choose)\b", re.I), self._music_you_pick),
            (re.compile(r"\b(press play|play pause|pause music|resume music|toggle music|media play|media pause)\b", re.I), self._media_play_pause),
            (re.compile(r"\bimport steam library\b|\bscan steam games\b", re.I), self._import_steam_library),
            (re.compile(r"\b(?:launch|open|start|play)\s+(.+?)\s+(?:on|in|through|with)\s+steam\b", re.I), self._launch_steam_game),
            (re.compile(r"\bremember(?: that)?\s+(.+)", re.I | re.S), self._remember_fact),
            (re.compile(r"\b(?:what do you remember|show memories|list memories|what have you remembered)\b", re.I), self._list_memories),
            (re.compile(r"\bforget(?: memory)?\s+(.+)", re.I | re.S), self._forget_memory),
            (re.compile(r"\bclear (?:all )?memories\b", re.I), self._clear_memories),
            (re.compile(r"\b(?:clear|empty)\s+(?:my\s+)?recycle bin\b", re.I), self._request_empty_recycle_bin),
            (re.compile(r"\b(play|start)\s+(?:the\s+song\s+|song\s+|track\s+)?(.+)", re.I), self._play_requested_music),
            (re.compile(r"\b(?:volume|sound)\s+(up|down|mute)\b|\b(mute|unmute)\s+(?:volume|sound|audio)\b", re.I), self._volume_control),
            (re.compile(r"\b(?:minimize|hide)\s+(?:this|current|active)?\s*window\b", re.I), self._minimize_window),
            (re.compile(r"\b(?:maximize|enlarge)\s+(?:this|current|active)?\s*window\b", re.I), self._maximize_window),
            (re.compile(r"\b(?:restore|unmaximize)\s+(?:this|current|active)?\s*window\b", re.I), self._restore_window),
            (re.compile(r"\b(?:close|exit)\s+(?:this|current|active)?\s*window\b", re.I), self._request_close_window),
            (re.compile(r"\block\s+(?:my\s+)?(?:laptop|pc|computer|windows)\b", re.I), self._request_lock_pc),
            (re.compile(r"\b(?:copy|set)\s+(?:clipboard|the clipboard)\s+(?:to\s+)?(.+)", re.I | re.S), self._set_clipboard),
            (re.compile(r"\b(?:read|show|what(?:'s| is) on)\s+(?:my\s+)?clipboard\b", re.I), self._read_clipboard),
            (re.compile(r"\bpaste(?:\s+clipboard)?\b", re.I), self._paste_clipboard),
            (re.compile(r"\btype\s+(.+)", re.I | re.S), self._type_text),
            (re.compile(r"\bpress\s+(enter|return|escape|esc|tab|space|backspace|delete|up|down|left|right)\b", re.I), self._press_key),
            (re.compile(r"\b(?:where(?:'s| is)?|show|tell me)\s+(?:my\s+)?mouse\b|\bmouse position\b", re.I), self._mouse_position),
            (re.compile(r"\bmove\s+(?:my\s+|the\s+)?mouse\s+to\s+(center|centre|middle|top left|top right|bottom left|bottom right)\b", re.I), self._move_mouse_named_position),
            (re.compile(r"\bmove\s+(?:my\s+|the\s+)?mouse\s+(left|right|up|down)(?:\s+(\d{1,4}))?\b", re.I), self._move_mouse_relative),
            (re.compile(r"\bmove\s+(?:my\s+|the\s+)?mouse\b", re.I), self._move_mouse_help),
            (re.compile(r"\bmove\s+(?:the\s+)?mouse\s+to\s+(\d{1,5})\s*,?\s+(\d{1,5})\b", re.I), self._move_mouse),
            (re.compile(r"\b(?:(double|right)\s+)?click(?:\s+at)?\s+(\d{1,5})\s*,?\s+(\d{1,5})\b", re.I), self._click_at),
            (re.compile(r"\bscroll\s+(up|down)(?:\s+(\d{1,2}))?\b", re.I), self._scroll_mouse),
            (re.compile(r"\b(?:list|show)\s+(?:open\s+)?windows\b", re.I), self._list_windows),
            (re.compile(r"\b(?:switch|focus|go)\s+to\s+(?:window\s+)?(.+)", re.I), self._switch_window),
            (re.compile(r"\bopen\s+(desktop|downloads|documents|pictures|music|videos|screenshots|project|jarvis)\s+folder\b", re.I), self._open_known_folder),
            (re.compile(r"\bcreate\s+(?:a\s+)?folder\s+(?:named\s+)?(.+?)\s+(?:on|in)\s+(desktop|downloads|documents|pictures|project|jarvis)\b", re.I), self._create_known_folder),
            (re.compile(r"\b(?:list|show)\s+(desktop|downloads|documents|pictures|music|videos|screenshots|project|jarvis)(?:\s+files)?\b", re.I), self._list_known_folder),
            (re.compile(r"\bopen\s+(?:the\s+)?(?:newest|latest|most recent)\s+(?:file\s+)?(?:in|from)\s+(desktop|downloads|documents|pictures|music|videos|screenshots|project|jarvis)\b", re.I), self._open_recent_file),
            (re.compile(r"\b(?:awareness|monitoring|proactive mode)\s+(on|off|enable|disable)\b|\b(?:enable|disable|turn on|turn off)\s+(?:awareness|monitoring|proactive mode)\b", re.I), self._set_awareness_mode),
            (re.compile(r"\b(?:awareness status|monitoring status|what are you monitoring|proactive status)\b", re.I), self._awareness_status),
            (re.compile(r"\b(?:watch|monitor)\s+(?:project\s+|folder\s+)?(.+)", re.I), self._watch_project_folder),
            (re.compile(r"\b(?:list|show)\s+(?:watched|monitored)\s+(?:projects|folders)\b|\bproject watcher status\b", re.I), self._project_watcher_status),
            (re.compile(r"\b(?:remove|unwatch|stop watching)\s+(?:project\s+|folder\s+)?(.+)", re.I), self._unwatch_project_folder),
            (re.compile(r"\b(?:project watcher|error watcher)\s+(on|off|enable|disable)\b|\b(?:enable|disable|turn on|turn off)\s+(?:project watcher|error watcher)\b", re.I), self._set_project_watcher_mode),
            (re.compile(r"\b(?:system info|pc status|laptop status|computer status|cpu and ram|cpu usage|ram usage|disk usage)\b", re.I), self._system_info),
            (re.compile(r"\bopen\s+(wifi|wi-fi|bluetooth|sound|audio|display|microphone|privacy|apps|windows update)\s+settings\b", re.I), self._open_windows_settings),
            (re.compile(r"\b(?:set|save|remember)\s+my\s+(?:current\s+)?location\s+(?:as|to)\s+(.+)", re.I), self._set_manual_location),
            (re.compile(r"\b(?:clear|forget|remove)\s+my\s+(?:saved\s+)?location\b", re.I), self._clear_manual_location),
            (re.compile(r"\b(?:enable|turn on)\s+(?:auto\s+)?(?:startup\s+)?location\b|\bauto\s+set\s+my\s+location\s+(?:on|at)\s+startup\b", re.I), self._enable_startup_location),
            (re.compile(r"\b(?:disable|turn off)\s+(?:auto\s+)?(?:startup\s+)?location\b|\bstop\s+auto\s+setting\s+my\s+location\b", re.I), self._disable_startup_location),
            (re.compile(r"\b(?:enable|turn on)\s+(?:approximate\s+)?(?:ip\s+)?location\b", re.I), self._enable_ip_location),
            (re.compile(r"\b(?:disable|turn off)\s+(?:approximate\s+)?(?:ip\s+)?location\b", re.I), self._disable_ip_location),
            (re.compile(r"\b(?:location diagnostics|maps diagnostics|maps status|location status)\b", re.I), self._location_diagnostics),
            (re.compile(r"\b(?:where am i|what(?:'s| is) my location|current location)\b", re.I), self._current_location),
            (re.compile(r"\b(?:directions|route)\s+from\s+(.+?)\s+to\s+(.+)", re.I | re.S), self._directions_from_to),
            (re.compile(r"\b(?:directions|route|navigate)\s+to\s+(.+)", re.I | re.S), self._directions_to),
            (re.compile(r"\b(?:eta|how long(?: will it take)?|travel time)\s+(?:to|get to|for)\s+(.+)", re.I | re.S), self._eta_to),
            (re.compile(r"\b(?:closest|nearest|nearby)\s+(.+?)\s*(?:near me|around me|by me)?$", re.I | re.S), self._directions_to_nearby_place),
            (re.compile(r"^(.+?)\s+(?:near me|around me|by me)$", re.I | re.S), self._directions_to_nearby_place),
            (re.compile(r"\bopen\s+(.+)", re.I), self._open_target),
            (re.compile(r"\b(search google for|google)\s+(.+)", re.I), self._google_search),
            (re.compile(r"\b(search youtube for|youtube)\s+(.+)", re.I), self._youtube_search),
            (re.compile(r"\b(time|what time is it)\b", re.I), self._time),
            (re.compile(r"\b(date|what day is it)\b", re.I), self._date),
            (re.compile(r"\bbattery\b", re.I), self._battery),
            (re.compile(r"\b(internet|online|connection)\b", re.I), self._internet),
            (re.compile(r"\b(screenshot|screen shot)\b", re.I), self._screenshot),
            (re.compile(r"\bjoke\b", re.I), self._joke),
            (re.compile(r"\bsummarize(?: this| what i typed)?[: ]+(.+)", re.I | re.S), self._summarize),
            (re.compile(r"\b(to-do|todo|task list).*(?:for|:)\s*(.+)", re.I | re.S), self._todo),
            (re.compile(r"\b(focus timer|timer)\s*(?:for)?\s*(\d+)?\s*(minute|minutes|min)?", re.I), self._focus_timer),
        ]

    def handle_command(self, user_text: str) -> tuple[str, str]:
        clean_text = self._strip_wake_phrase(user_text.strip())
        if not clean_text:
            return "system", "I heard the wake phrase, but not the part where you gave me a mission."

        confirmation_response = self._handle_confirmation(clean_text)
        if confirmation_response is not None:
            return "action", confirmation_response

        pending_navigation_response = self._handle_pending_navigation_request(clean_text)
        if pending_navigation_response is not None:
            return "action", pending_navigation_response

        pending_music_response = self._handle_pending_music_request(clean_text)
        if pending_music_response is not None:
            return "action", pending_music_response

        pending_music_device_response = self._handle_pending_music_device_request(clean_text)
        if pending_music_device_response is not None:
            return "action", pending_music_device_response

        safe_mode_response = self._handle_safe_mode_confirmation_needed(clean_text)
        if safe_mode_response is not None:
            return "action", safe_mode_response

        for pattern, handler in self.command_handlers:
            match = pattern.search(clean_text)
            if match:
                try:
                    return "action", handler(match, clean_text)
                except Exception as exc:
                    return "error", f"I'm sorry, but I am unable to process your request at this time. Technical indignity: {exc}"

        if self._should_use_screen_vision(clean_text):
            return "action", self.analyze_screen_with_gemini(clean_text)

        if self.settings.get("agent_tools_enabled", True) and self._should_use_agent_tools(clean_text):
            return "action", self.run_agent_task(clean_text)

        return "assistant", self.ask_ai(clean_text)

    def record_action(self, action: str, args: Any, risk: str, success: bool, message: str, verified: bool | None = None) -> None:
        if verified is None:
            verified = success
        entry = {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "action": str(action),
            "args": args if isinstance(args, dict) else {},
            "risk": str(risk or "safe"),
            "success": bool(success),
            "verified": bool(verified),
            "message": str(message)[:500],
        }
        self.action_ledger.append(entry)
        self.action_ledger = self.action_ledger[-30:]
        self.last_action = entry["action"]
        self.last_risk = entry["risk"]
        state = "verified" if entry["verified"] and entry["success"] else ("failed" if not entry["success"] else "unverified")
        self.last_verified_action = f"{entry['action']} - {state}"

    def action_message_indicates_success(self, message: str) -> bool:
        lowered = message.lower()
        failure_terms = [
            "could not",
            "couldn't",
            "failed",
            "failure",
            "not found",
            "unavailable",
            "rejected",
            "refused",
            "did not complete",
            "did not press",
            "cannot",
            "can't",
            "error",
        ]
        return not any(term in lowered for term in failure_terms)

    def _action_history(self, _match: re.Match[str], _text: str) -> str:
        if not self.action_ledger:
            return "No actions recorded yet. Astonishing restraint."
        lines = ["Recent verified action ledger:"]
        for entry in reversed(self.action_ledger[-8:]):
            status = "verified" if entry["verified"] and entry["success"] else ("failed" if not entry["success"] else "unverified")
            lines.append(f"- {entry['timestamp']} | {entry['action']} | {status} | risk={entry['risk']} | {entry['message']}")
        return "\n".join(lines)

    def _handle_confirmation(self, clean_text: str) -> str | None:
        if self.pending_confirmation is None:
            return None

        lowered = clean_text.lower().strip()
        if lowered in {"cancel", "no", "nope", "stop", "never mind", "nevermind"}:
            action = str(self.pending_confirmation.get("label", "that action"))
            self.pending_confirmation = None
            return f"Cancelled {action}. Caution, for once, has won."

        if lowered not in {"yes", "confirm", "confirmed", "do it", "proceed", "go ahead"}:
            return None

        pending = self.pending_confirmation
        self.pending_confirmation = None
        action = pending.get("action")
        if action == "close_window":
            title = get_active_window_title()
            if close_active_window():
                return f"Closed the active window: {title}."
            return "I tried to close the active window, but Windows declined the gesture."
        if action == "lock_pc":
            if lock_windows_workstation():
                return "Locking the laptop. Very dramatic. Very secure."
            return "I tried to lock Windows, but the system refused."
        if action == "empty_recycle_bin":
            success, message = clear_recycle_bin()
            if success:
                self.record_action("empty_recycle_bin", {}, "high", True, message, verified=True)
                return "Recycle Bin cleared. The digital clutter has been escorted out."
            failure_message = f"I tried to clear the Recycle Bin, but it did not complete. {message}"
            self.record_action("empty_recycle_bin", {}, "high", False, failure_message, verified=True)
            return failure_message
        if action == "agent_tool":
            call = pending.get("tool_call")
            if isinstance(call, dict):
                observation = self.tool_registry.execute(call)
                return f"Confirmed. {observation}"
            return "The pending agent tool call was malformed, so I refused to run it."
        if action == "agent_message":
            return str(pending.get("message", "Confirmed."))
        if action == "safe_mode_command":
            text = str(pending.get("text", ""))
            if text:
                previous_mode = self.current_mode
                self.current_mode = "Normal"
                try:
                    _role, response = self.handle_command(text)
                finally:
                    self.current_mode = previous_mode
                return f"Confirmed under Safe Mode. {response}"
            return "Confirmed, but the stored Safe Mode action was empty."
        return "That pending action expired into mystery. Probably for the best."

    def _handle_safe_mode_confirmation_needed(self, clean_text: str) -> str | None:
        if self.current_mode.lower() != "safe":
            return None
        lowered = clean_text.lower()
        if lowered in {"confirm", "cancel", "yes", "no", "do it", "go ahead"}:
            return None
        guarded_terms = ["click", "double click", "right click", "type ", "press ", "hotkey", "paste", "move file", "delete file"]
        if not any(term in lowered for term in guarded_terms):
            return None
        self.pending_confirmation = {
            "action": "safe_mode_command",
            "label": "Safe Mode guarded action",
            "text": clean_text,
        }
        return "Safe Mode is active. That action can affect the computer directly, so I need confirmation first."

    def _should_use_screen_vision(self, clean_text: str) -> bool:
        lowered = clean_text.lower()
        if "apple music" in lowered or "music app" in lowered:
            return False
        screen_terms = ["screen", "page", "window", "button", "click", "visible", "looking at", "see this"]
        intent_terms = ["what", "where", "which", "read", "find", "help me", "tell me", "analyze", "explain"]
        return any(term in lowered for term in screen_terms) and any(term in lowered for term in intent_terms)

    def _should_use_agent_tools(self, clean_text: str) -> bool:
        lowered = clean_text.lower()
        if lowered.startswith(("agent ", "use tools ", "tool mode ")):
            return True
        coding_agent_terms = [
            "search the code", "search code", "search my project", "inspect my code",
            "inspect the project", "diagnose my code", "diagnose the project",
            "read code file", "read the code file", "run code check", "run project tests",
            "run the tests", "what kind of project", "coding workspace status",
        ]
        if any(term in lowered for term in coding_agent_terms):
            return True
        action_terms = [
            "open ",
            "click",
            "type ",
            "press ",
            "scroll",
            "switch to",
            "search web",
            "search google",
            "list folder",
            "open file",
            "create folder",
            "move file",
            "delete file",
            "take screenshot",
            "analyze screen",
            "directions",
            "route",
            "eta",
            "location",
        ]
        multi_step_terms = [" then ", " and then ", "after that", "figure out", "do this", "complete this", "use my screen"]
        return any(term in lowered for term in action_terms) and any(term in lowered for term in multi_step_terms)

    def run_agent_task(self, user_text: str) -> str:
        if genai is None or self.gemini_client is None:
            return "Agent tools need Gemini configured. The tool registry is ready, but the planner has no uplink."

        max_steps = max(1, min(10, int(self.settings.get("agent_max_steps", 6))))
        observations: list[str] = []
        executed: list[str] = []
        for step in range(1, max_steps + 1):
            call = self._ask_gemini_for_tool_call(user_text, observations, step)
            action = str(call.get("action", "")).strip()
            if action == "final":
                summary = str(call.get("args", {}).get("summary", "Task complete.")).strip()
                if executed:
                    return f"{summary}\n\nTask summary:\n" + "\n".join(f"- {item}" for item in executed)
                return summary

            ok, error, tool = self.tool_registry.validate(call)
            if not ok or tool is None:
                observations.append(f"Step {step}: rejected invalid tool call. {error}")
                continue

            reason = str(call.get("reason", "No reason supplied.")).strip()
            if self.tool_registry.requires_confirmation(call, tool):
                self.pending_confirmation = {
                    "action": "agent_tool",
                    "label": action,
                    "tool_call": call,
                }
                return (
                    f"I need confirmation before using `{action}`.\n"
                    f"Reason: {reason}\n"
                    "Say `confirm` to run it, or `cancel` to stop."
                )

            observation = self.tool_registry.execute(call)
            executed.append(f"{action}: {observation}")
            observations.append(f"Step {step} tool={action} reason={reason} observation={observation}")

            if action == "cancel_task":
                return f"Task cancelled.\n\nTask summary:\n" + "\n".join(f"- {item}" for item in executed)

        if executed:
            return "I reached the agent step limit before declaring victory. Here is what I did:\n" + "\n".join(f"- {item}" for item in executed)
        return "I could not find a safe approved tool path for that request."

    def _ask_gemini_for_tool_call(self, user_text: str, observations: list[str], step: int) -> dict[str, Any]:
        context = {
            "user_request": user_text,
            "step": step,
            "current_active_window": get_active_window_title(),
            "coding_workspace": str(self.settings.get("coding_workspace_folder", "")) or "not selected",
            "tools": self.tool_registry.descriptions(),
            "observations": observations[-8:],
            "permission_mode": str(self.settings.get("agent_permission_mode", "Ask for approval")),
            "assistant_mode": self.current_mode,
            "safety_rules": [
                "Only use approved tools.",
                "Safe actions may run immediately.",
                "Declare every action risk honestly; the local permission policy decides confirmation.",
                "Ask for approval confirms medium and high risk actions.",
                "Approve for me confirms high risk actions only.",
                "Full access may auto-run approved tools, but Safe Mode still overrides it.",
                "Never run arbitrary terminal commands.",
                "Never delete files, send messages, buy things, change passwords, or enter private info without confirmation.",
            ],
        }
        prompt = (
            f"{AGENT_SYSTEM_PROMPT}\n\n"
            "Context JSON:\n"
            f"{json.dumps(context, indent=2)}"
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(system_instruction=AGENT_SYSTEM_PROMPT),
                )
                raw_text = getattr(response, "text", "").strip()
                match = re.search(r"\{.*\}", raw_text, flags=re.S)
                if not match:
                    return {"action": "final", "args": {"summary": f"Gemini did not return a usable tool call: {raw_text[:180]}"}, "risk": "safe", "reason": "unusable planner output"}
                return json.loads(match.group(0))
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return {"action": "final", "args": {"summary": f"Agent planner was unavailable: {last_error}"}, "risk": "safe", "reason": "planner unavailable"}

    def _handle_pending_music_request(self, clean_text: str) -> str | None:
        if self.pending_music_request is None:
            return None
        lowered = clean_text.lower().strip()
        if lowered in {"cancel", "no", "never mind", "nevermind", "stop"}:
            self.pending_music_request = None
            return "Cancelled the pending music request."
        if len(clean_text) < 2:
            return None
        pending = self.pending_music_request
        self.pending_music_request = None
        app = str(pending.get("app", "apple_music"))
        if app == "apple_music":
            return self._play_apple_music_query(clean_text)
        return None

    def _handle_pending_music_device_request(self, clean_text: str) -> str | None:
        if self.pending_music_device_request is None:
            return None
        lowered = clean_text.lower().strip()
        if lowered in {"cancel", "no", "never mind", "nevermind", "stop"}:
            self.pending_music_device_request = None
            return "Cancelled the pending music request."
        pending = self.pending_music_device_request
        if any(term in lowered for term in ["phone", "mobile", "iphone", "my device"]):
            self.pending_music_device_request = None
            return self._play_mobile_apple_music_query(str(pending.get("query", "")))
        if any(term in lowered for term in ["this device", "computer", "pc", "laptop", "desktop", "here"]):
            self.pending_music_device_request = None
            return self._play_apple_music_query(str(pending.get("query", "")))
        return None

    def _handle_pending_navigation_request(self, clean_text: str) -> str | None:
        if self.pending_navigation_request is None:
            return None
        lowered = clean_text.lower().strip()
        if lowered in {"cancel", "no", "nope", "stop", "never mind", "nevermind"}:
            destination = str(self.pending_navigation_request.get("label") or self.pending_navigation_request.get("destination", "that place"))
            self.pending_navigation_request = None
            return f"Navigation cancelled for {destination}."
        if lowered not in {"yes", "yeah", "yep", "sure", "confirm", "do it", "go ahead", "please do"}:
            return None
        pending = self.pending_navigation_request
        self.pending_navigation_request = None
        destination = str(pending.get("destination", "")).strip()
        if not destination:
            return "I had a navigation request queued, but the destination went missing. Very stylish, not useful."
        origin = str(pending.get("origin", "")).strip()
        mode = str(pending.get("mode", "")).strip()
        return self._open_directions_to_destination(destination, origin=origin or None, mode=mode or None)

    def _maybe_queue_navigation_offer(self, user_text: str, assistant_text: str) -> None:
        lowered_response = assistant_text.lower()
        if not any(term in lowered_response for term in ["pull up navigation", "open navigation", "open directions", "start navigation", "directions to"]):
            return
        if "?" not in assistant_text and not any(term in lowered_response for term in ["should i", "would you like", "want me to"]):
            return
        destination = self._navigation_destination_from_text(user_text)
        if destination:
            self.pending_navigation_request = {
                "destination": destination,
                "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            }

    def _navigation_destination_from_text(self, text: str) -> str:
        cleaned = self._strip_wake_phrase(text).strip().strip("?!.")
        cleaned = re.sub(r"\b(?:closest|nearest|nearby)\b", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"\b(?:near me|around me|by me)\b", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"\b(?:find|search for|look up|where(?:'s| is)|show me|directions to|navigate to|route to)\b", "", cleaned, flags=re.I).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
        if not cleaned:
            return ""
        blocked = {"yes", "no", "location", "current location", "directions", "navigation"}
        if cleaned.lower() in blocked:
            return ""
        return cleaned[:120]

    def ask_ai(self, user_text: str) -> str:
        provider = str(self.settings.get("ai_provider", "gemini")).lower()
        if provider == "gemini":
            return self.ask_gemini(user_text)
        return self.ask_openai(user_text)

    def review_document_text(self, document_text: str, source_title: str = "") -> str:
        if genai is None or genai_types is None or self.gemini_client is None:
            return "I can read the document aloud, but the Gemini service is unavailable for critique right now."
        max_chars = max(4000, int(self.settings.get("document_review_max_chars", 32000)))
        trimmed = document_text[:max_chars]
        truncated = len(document_text) > len(trimmed)
        prompt = (
            "You are JARVIS helping the user revise a novel draft. Give honest, specific, constructive writing feedback. "
            "Do not rewrite the whole piece. Focus on craft. Be encouraging but not fake. "
            "Use concise sections:\n"
            "1. What you did well\n"
            "2. What to work on\n"
            "3. Strongest moment\n"
            "4. Next revision moves\n"
            "5. One polished JARVIS-style closing line\n\n"
            f"Active window/source title: {source_title or 'Unknown'}\n"
            f"Document was truncated for review: {'yes' if truncated else 'no'}\n\n"
            "Draft text:\n"
            f"{trimmed}"
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=(
                            "You are a sharp but supportive novel editor with a polished, lightly witty assistant voice. "
                            "Be honest about weaknesses and specific about strengths."
                        )
                    ),
                )
                text = getattr(response, "text", "").strip()
                if truncated:
                    text += "\n\nNote: I reviewed the first portion of the document because the full text was very long."
                return text or "I read it, but Gemini returned an empty critique. An ominous silence, frankly."
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return f"I finished reading, but Gemini feedback failed: {last_error}"

    def explain_code_file(self, relative_path: str, file_text: str, question: str) -> str:
        if genai is None or genai_types is None or self.gemini_client is None:
            return "Code explanation needs Gemini configured. The workspace browser itself remains available offline."
        trimmed = file_text[:30000]
        was_truncated = len(file_text) > len(trimmed)
        prompt = (
            "Act as JARVIS in Coding Mode: a concise, capable code mentor. Analyze only the supplied file. "
            "Explain behavior with specific references to functions, classes, or sections. Call out likely bugs "
            "or risks only when supported by the code. Do not claim to have edited or run anything. "
            "Use these sections when useful: Summary, How it works, Risks, Suggested next step.\n\n"
            f"File: {relative_path}\n"
            f"User question: {question or 'Explain this file and identify its main responsibilities.'}\n"
            f"File truncated: {'yes' if was_truncated else 'no'}\n\n"
            f"SOURCE CODE:\n{trimmed}"
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=(
                            "You are a careful senior software engineer helping through a futuristic desktop assistant. "
                            "Be accurate, approachable, and lightly witty. Never invent unseen files or executed results."
                        )
                    ),
                )
                answer = getattr(response, "text", "").strip()
                if answer:
                    return answer
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                break
        return f"I could not analyze that file right now. Gemini reported: {last_error}"
    def propose_code_edit(self, relative_path: str, file_text: str, request: str) -> dict[str, Any]:
        if genai is None or genai_types is None or self.gemini_client is None:
            return {"ok": False, "error": "Code editing needs Gemini configured."}
        if not request.strip():
            return {"ok": False, "error": "Describe the change you want first."}
        normalized_source = file_text.replace("\r\n", "\n").replace("\r", "\n")
        if len(normalized_source) > 50000:
            return {"ok": False, "error": "That file is too large for a reliable whole-file edit. Phase 2 limits editable files to 50,000 characters."}
        prompt = (
            "Propose one careful edit to the supplied source file. Preserve all unrelated behavior and formatting. "
            "Return JSON only, with exactly these keys: summary (short string) and updated_content (the complete updated file). "
            "Do not use Markdown fences. Do not omit unchanged sections. Do not claim to run tests.\n\n"
            f"File: {relative_path}\n"
            f"Requested change: {request}\n\n"
            f"CURRENT COMPLETE FILE:\n{normalized_source}"
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=(
                            "You are a conservative senior coding assistant. Return valid JSON only. "
                            "Make the smallest correct change and preserve all unrelated code."
                        ),
                        response_mime_type="application/json",
                    ),
                )
                raw = getattr(response, "text", "").strip()
                start = raw.find("{")
                if start < 0:
                    raise ValueError("Gemini returned no JSON object")
                proposal, _end = json.JSONDecoder().raw_decode(raw[start:])
                summary = str(proposal.get("summary", "Proposed code update.")).strip()
                updated = proposal.get("updated_content")
                if not isinstance(updated, str) or not updated.strip():
                    raise ValueError("Gemini omitted updated_content")
                updated = updated.replace("\r\n", "\n").replace("\r", "\n")
                if updated == normalized_source:
                    return {"ok": False, "error": "Gemini proposed no actual changes."}
                return {"ok": True, "summary": summary[:500], "updated_content": updated}
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                break
        return {"ok": False, "error": f"Gemini could not prepare a valid edit: {last_error}"}
    def _build_context(self, user_text: str) -> str:
        window_title = get_active_window_title()
        context_lines = [
            f"User name: {self.settings.get('user_name') or 'not provided'}",
            f"Preferred user name/personality file: {self.personality.get('user_name') or 'not provided'}",
            f"Assistant name: {self.personality.get('assistant_name', 'J.A.R.V.I.S.')}",
            f"Assistant mode: {self.current_mode}",
            f"Sarcasm level 0-5: {self.personality.get('sarcasm_level', 3)}",
            f"Formality: {self.personality.get('formality', 'polished')}",
            f"Operating system: {platform.platform()}",
            f"Current active window: {window_title}",
            self._build_self_awareness_context(),
            "Saved local memories, explicitly saved by the user and not chat transcripts:",
        ]
        if self.memories:
            for memory in self.memories[-12:]:
                context_lines.append(f"- {memory['text']}")
        else:
            context_lines.append("- None saved")
        context_lines.append("Recent conversation, temporary only and not saved to disk:")
        for item in self.history[-self.max_history :]:
            context_lines.append(f"{item['role']}: {item['content']}")
        context_lines.append(f"User: {user_text}")
        return "\n".join(context_lines)

    def _build_self_awareness_context(self) -> str:
        enabled_integrations: list[str] = []
        disabled_integrations: list[str] = []
        for key, details in INTEGRATION_CATALOG.items():
            label = str(details.get("name") or key)
            if integration_enabled(self.settings, key):
                enabled_integrations.append(label)
            else:
                disabled_integrations.append(label)

        recent_failures = [
            entry for entry in self.action_ledger[-20:]
            if not bool(entry.get("success", False)) or not bool(entry.get("verified", False))
        ][-5:]
        failure_lines = [
            f"- {entry.get('action', 'unknown action')}: {str(entry.get('message', 'failed'))[:180]}"
            for entry in recent_failures
        ] or ["- No verified failures recorded during this session."]

        capability_lines = [
            "Operational self-awareness:",
            "Currently supported:",
            "- Voice and text conversation; voice availability still depends on Windows microphone and speech services.",
            "- Approved local tools for screen capture/analysis, mouse and keyboard control, app launching, web access, files, music, and window management.",
            f"- Gemini reasoning and vision: {'connected' if self.gemini_client is not None else 'offline'}.",
            f"- Agent tools: {'enabled' if self.settings.get('agent_tools_enabled', True) else 'disabled'}; permission mode is {self.settings.get('agent_permission_mode', 'Ask for approval')}.",
            f"- Enabled integrations: {', '.join(enabled_integrations) if enabled_integrations else 'none'}.",
            f"- Available but disabled/unconfigured integrations: {', '.join(disabled_integrations[:12]) if disabled_integrations else 'none'}.",
            "Known limitations:",
            "- No arbitrary terminal execution and no actions outside approved tools.",
            "- Screen understanding uses snapshots, not continuous perfect visual awareness.",
            "- Apple Music and other desktop apps may require UI automation; success must be visually or locally verified.",
            "- No consciousness, emotions, physical body, neural link, or independent hardware autonomy.",
            "- Purchases, messages, passwords, destructive file actions, and risky settings changes require confirmation.",
            "Recent unverified or failed actions:",
            *failure_lines,
        ]
        return "\n".join(capability_lines)

    def ask_gemini(self, user_text: str) -> str:
        if genai is None or genai_types is None:
            return "Gemini support is not installed. Run pip install -r requirements.txt, then try again."
        if self.gemini_client is None:
            return "Gemini is not configured. Check the JARVIS AI service connection and try again."

        models_to_try, intentional_fast_route = self._gemini_chat_models_to_try(user_text)
        last_error = None
        fallback_used = None

        try:
            text = ""
            for model in models_to_try:
                try:
                    response = self.gemini_client.models.generate_content(
                        model=model,
                        contents=self._build_context(user_text),
                        config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                    )
                    text = getattr(response, "text", "").strip()
                    if text:
                        if model != self.settings.get("gemini_model") and not (intentional_fast_route and model == models_to_try[0]):
                            fallback_used = model
                            self.settings["gemini_model"] = model
                            save_settings(self.settings)
                        break
                except Exception as exc:
                    last_error = exc
                    if self._is_recoverable_gemini_error(exc):
                        continue
                    raise
            if not text:
                if last_error:
                    text = f"I'm sorry, but Gemini is unavailable right now. Temporary cloud drama: {last_error}"
                else:
                    text = "I'm sorry, but I am unable to process your request at this time."
            elif fallback_used:
                text = f"{text}\n\n[System note: The first Gemini model refused the job, so I switched to {fallback_used}.]"
        except Exception as exc:
            text = f"I'm having trouble reaching Gemini. The uplink is sulking. ({exc})"

        self._remember("user", user_text)
        self._remember("assistant", text)
        self._maybe_queue_navigation_offer(user_text, text)
        return text

    def transcribe_audio_with_gemini(self, audio: sr.AudioData) -> str:
        if genai is None or genai_types is None or self.gemini_client is None:
            raise RuntimeError("Gemini transcription is not configured")

        wav_bytes = audio_data_to_wav_bytes(audio, target_rate=16000)
        prompt = (
            "Transcribe this spoken command exactly. Return only the words spoken by the user. "
            "Do not add punctuation unless it is obvious. If there is no intelligible speech, return an empty string."
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=wav_bytes, mime_type="audio/wav"),
                    ],
                )
                text = getattr(response, "text", "").strip()
                text = re.sub(r"^(transcription|transcript)\s*:\s*", "", text, flags=re.I).strip()
                return text.strip("\"' \n\r\t")
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        raise RuntimeError(f"Gemini transcription failed: {last_error}")

    def analyze_screen_with_gemini(self, user_text: str) -> str:
        if genai is None or genai_types is None:
            return "Gemini support is not installed, so I cannot analyze the screen yet."
        if self.gemini_client is None:
            return "Gemini is not configured, so screen vision is unavailable. Check the JARVIS AI service connection."

        try:
            png_bytes, original_size = capture_screen_png()
        except Exception as exc:
            return (
                "I couldn't capture the screen from this Windows session. "
                f"Screen vision is blocked by the capture API right now: {exc}"
            )
        prompt = (
            f"{self._build_context(user_text)}\n\n"
            f"Screen capture size before resizing: {original_size[0]}x{original_size[1]}.\n"
            "Analyze the attached screenshot. Describe what is visible, identify important buttons, menus, text fields, "
            "warnings, selected items, and likely next steps. If the user asks where to click, give a practical target "
            "description and approximate location such as top-left, center, or bottom-right; do not claim to click anything. "
            "Be concise, useful, and keep the JARVIS tone light."
        )
        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                    ],
                    config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                text = getattr(response, "text", "").strip()
                if text:
                    self._remember("user", user_text)
                    self._remember("assistant", text)
                    return text
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return f"I tried to inspect the screen, but Gemini vision was unavailable. ({last_error})"

    def locate_apple_music_play_target(self, query: str) -> tuple[bool, str, int | None, int | None]:
        if genai is None or genai_types is None or self.gemini_client is None:
            return False, "Gemini vision is not configured.", None, None
        try:
            png_bytes, original_size = capture_screen_png()
        except Exception as exc:
            return False, f"Screen capture failed: {exc}", None, None

        prompt = (
            "You are helping control Apple Music on Windows from a screenshot.\n"
            f"The user requested this exact song/search: {query!r}.\n"
            f"The screenshot's original screen size is {original_size[0]}x{original_size[1]} pixels.\n"
            "Find the visible Apple Music search result that best matches the requested song and artist.\n"
            "Prefer a SONG/TRACK result. Do not choose playlists, albums, artist pages, essentials collections, radio, or unrelated tracks.\n"
            "If the exact song result is visible, return coordinates for its play button if visible; otherwise return coordinates near the matching song row/title that would open/play it.\n"
            "Never return coordinates on the vertical scrollbar, page scroll area, far-right edge, sidebar navigation, or window chrome. "
            "The x coordinate should be inside the song result row/play/title area, usually well left of the right edge.\n"
            "Return only compact JSON with this schema: "
            "{\"found\":true|false,\"x\":number|null,\"y\":number|null,\"confidence\":0-100,\"reason\":\"short\"}.\n"
            "The x and y must be in original screen coordinates, not resized image coordinates. If unsure, set found false."
        )

        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                    ],
                    config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                raw_text = getattr(response, "text", "").strip()
                match = re.search(r"\{.*\}", raw_text, flags=re.S)
                if not match:
                    return False, f"Vision response was not usable: {raw_text[:160]}", None, None
                data = json.loads(match.group(0))
                found = bool(data.get("found"))
                confidence = int(float(data.get("confidence", 0) or 0))
                reason = str(data.get("reason", "")).strip()[:220]
                x_value = data.get("x")
                y_value = data.get("y")
                if not found or confidence < 65 or x_value is None or y_value is None:
                    return False, reason or "Gemini vision could not verify the exact song result.", None, None
                x, y = clamp_screen_point(int(float(x_value)), int(float(y_value)))
                width, height = original_size
                if x > width - 150:
                    safe_x = max(180, min(width // 3, width - 220))
                    return (
                        True,
                        f"Vision pointed near the scrollbar, so I used the safer song-row position at x={safe_x}. {reason}",
                        safe_x,
                        y,
                    )
                if y < 90 or y > height - 50:
                    return (
                        False,
                        f"Vision target was outside the safe Apple Music content area, so I refused to click it. {reason}",
                        None,
                        None,
                    )
                return True, reason or f"Vision located a target with {confidence}% confidence.", x, y
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return False, f"Gemini vision could not locate the play target: {last_error}", None, None

    def locate_apple_music_visible_play_button(self, query: str) -> tuple[bool, str, int | None, int | None]:
        if genai is None or genai_types is None or self.gemini_client is None:
            return False, "Gemini vision is not configured.", None, None
        try:
            png_bytes, original_size = capture_screen_png()
        except Exception as exc:
            return False, f"Screen capture failed: {exc}", None, None

        prompt = (
            "You are helping control Apple Music on Windows from a screenshot after a search result was selected.\n"
            f"The user requested this exact song/search: {query!r}.\n"
            f"The screenshot's original screen size is {original_size[0]}x{original_size[1]} pixels.\n"
            "Find the visible Play button that would start playback for the selected matching song, song page, album page, "
            "or opened result. Prefer the large/main play button near the selected result or page header.\n"
            "Do not choose the vertical scrollbar, page scroll area, far-right edge, sidebar navigation, window chrome, "
            "AirPlay, replay, mini-player controls, or unrelated top navigation buttons.\n"
            "Return the center of the Play button, not the song title text and not an empty part of the row.\n"
            "Return only compact JSON with this schema: "
            "{\"found\":true|false,\"x\":number|null,\"y\":number|null,\"confidence\":0-100,\"reason\":\"short\"}.\n"
            "The x and y must be in original screen coordinates, not resized image coordinates. If unsure, set found false."
        )

        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                    ],
                    config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                raw_text = getattr(response, "text", "").strip()
                match = re.search(r"\{.*\}", raw_text, flags=re.S)
                if not match:
                    return False, f"Vision response was not usable: {raw_text[:160]}", None, None
                data = json.loads(match.group(0))
                found = bool(data.get("found"))
                confidence = int(float(data.get("confidence", 0) or 0))
                reason = str(data.get("reason", "")).strip()[:220]
                x_value = data.get("x")
                y_value = data.get("y")
                if not found or confidence < 65 or x_value is None or y_value is None:
                    return False, reason or "Gemini vision could not verify a visible Play button.", None, None
                x, y = clamp_screen_point(int(float(x_value)), int(float(y_value)))
                width, height = original_size
                if x > width - 150:
                    return False, f"Vision target was too close to the scrollbar/right edge, so I refused to click it. {reason}", None, None
                if y < 90 or y > height - 80:
                    return False, f"Vision target was outside the safe Apple Music content area, so I refused to click it. {reason}", None, None
                return True, reason or f"Vision located a Play button with {confidence}% confidence.", x, y
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return False, f"Gemini vision could not locate the Play button: {last_error}", None, None

    def verify_apple_music_playback(self, query: str) -> tuple[bool, str]:
        if genai is None or genai_types is None or self.gemini_client is None:
            return False, "Gemini vision is not configured, so playback could not be verified."
        try:
            png_bytes, original_size = capture_screen_png()
        except Exception as exc:
            return False, f"Screen capture failed during playback verification: {exc}"

        prompt = (
            "You are verifying Apple Music playback on Windows from a screenshot.\n"
            f"The user requested this song/search: {query!r}.\n"
            f"The screenshot size is {original_size[0]}x{original_size[1]} pixels.\n"
            "Return whether music appears to be actively playing. Strong evidence includes a Pause button, animated/active "
            "now-playing controls, or the requested track visible in the now-playing area with playback active. "
            "Do not count a search result merely being selected as playback. If you only see a Play button, it is not verified.\n"
            "Return only compact JSON with this schema: "
            "{\"playing\":true|false,\"confidence\":0-100,\"reason\":\"short\"}."
        )

        last_error = None
        for model in self._gemini_models_to_try():
            try:
                response = self.gemini_client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
                    ],
                    config=genai_types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                raw_text = getattr(response, "text", "").strip()
                match = re.search(r"\{.*\}", raw_text, flags=re.S)
                if not match:
                    return False, f"Playback verification response was not usable: {raw_text[:160]}"
                data = json.loads(match.group(0))
                playing = bool(data.get("playing"))
                confidence = int(float(data.get("confidence", 0) or 0))
                reason = str(data.get("reason", "")).strip()[:220]
                if playing and confidence >= 65:
                    return True, reason or "Apple Music appears to be playing."
                return False, reason or "Apple Music playback was not visually verified."
            except Exception as exc:
                last_error = exc
                if self._is_recoverable_gemini_error(exc):
                    continue
                raise
        return False, f"Playback verification failed: {last_error}"

    def ask_openai(self, user_text: str) -> str:
        if self.openai_client is None:
            return (
                "OpenAI is not configured. Add OPENAI_API_KEY to your .env file and I can become "
                "properly insufferable."
            )

        try:
            request = {
                "model": self.settings.get("openai_model", "gpt-4.1-mini"),
                "instructions": SYSTEM_PROMPT,
                "input": self._build_context(user_text),
            }
            if self.settings.get("enable_openai_web_search", True):
                request["tools"] = [{"type": "web_search_preview"}]

            try:
                response = self.openai_client.responses.create(**request)
            except Exception:
                request.pop("tools", None)
                response = self.openai_client.responses.create(**request)

            text = getattr(response, "output_text", "").strip()
            if not text:
                text = "I'm sorry, but I am unable to process your request at this time."
        except Exception as exc:
            text = f"I'm having trouble reaching OpenAI. Even I require a working uplink. ({exc})"

        self._remember("user", user_text)
        self._remember("assistant", text)
        self._maybe_queue_navigation_offer(user_text, text)
        return text

    def _remember(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        self.history = self.history[-self.max_history :]

    def _strip_wake_phrase(self, text: str) -> str:
        wake_phrase = str(self.settings.get("wake_phrase", "jarvis")).lower()
        lowered = text.lower().strip()
        for phrase in [wake_phrase, f"hey {wake_phrase}"]:
            if lowered.startswith(phrase):
                return text[len(phrase) :].strip(" ,.")
        return text

    def _active_window(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        return f"You're currently in: {title}. Astonishingly, I noticed."

    def _look_at_screen(self, _match: re.Match[str], text: str) -> str:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        return self.analyze_screen_with_gemini(text)

    def _list_agent_tools(self, _match: re.Match[str], _text: str) -> str:
        lines = ["Approved agent tools:"]
        for tool in self.tool_registry.descriptions():
            lines.append(f"- {tool['name']} ({tool['risk']}): {tool['description']}")
        return "\n".join(lines)

    def _integrations_status(self, _match: re.Match[str], _text: str) -> str:
        lines = ["Integration status:"]
        grouped: dict[str, list[str]] = {}
        for key, meta in INTEGRATION_CATALOG.items():
            status, detail = integration_status(key, self.settings)
            category = str(meta.get("category", "Other"))
            enabled = "on" if integration_enabled(self.settings, key) else "off"
            grouped.setdefault(category, []).append(f"- {meta['name']}: {status} ({enabled}) - {detail}")
        for category in sorted(grouped):
            lines.append(f"\n{category}:")
            lines.extend(grouped[category])
        lines.append("\nOpen the Integrations panel to toggle these or jump to setup pages.")
        return "\n".join(lines)

    def _set_mode(self, match: re.Match[str], _text: str) -> str:
        mode = match.group(1).strip().title()
        if mode not in {"Normal", "Coding", "School", "Gaming", "Focus", "Safe"}:
            return f"I do not recognize {mode} mode."
        self.current_mode = mode
        self.settings["assistant_mode"] = mode
        self.settings["mouse_control_mode"] = "Disabled" if mode == "Safe" else "Safe"
        save_settings(self.settings)
        if mode == "Coding":
            return "Coding Mode online. I will keep the chatter lean and the diagnostics close."
        if mode == "School":
            return "School Mode active. Calm focus, fewer distractions, marginally fewer theatrics."
        if mode == "Gaming":
            return "Gaming Mode active. Performance and music cues are prioritized. Productivity has been informed."
        if mode == "Focus":
            return "Focus Mode active. I will keep responses brief and interruptions light."
        if mode == "Safe":
            return "Safe Mode active. Mouse clicks and typing now require confirmation. I will be careful."
        return "Normal Mode restored. Systems are ready."

    def _mode_status(self, _match: re.Match[str], _text: str) -> str:
        return (
            f"Mode: {self.current_mode}\n"
            f"Mouse Control: {self.settings.get('mouse_control_mode', 'Safe')}\n"
            f"Last action: {self.last_action}\n"
            f"Risk level: {self.last_risk}"
        )

    def _list_microphones(self, _match: re.Match[str], _text: str) -> str:
        devices = list_input_devices()
        if not devices:
            return "I couldn't find any microphone input devices."
        selected = self.settings.get("voice_input_device_index")
        lines = ["Available microphones:"]
        for device in devices:
            marker = " [selected]" if selected == device["index"] else ""
            lines.append(f"{device['index']}. {device['name']} ({device['sample_rate']} Hz){marker}")
        lines.append("Say `use microphone 15` with the number you want. I recommend trying a WASAPI or headset input if the default peak is 1.")
        return "\n".join(lines)

    def _set_microphone(self, match: re.Match[str], _text: str) -> str:
        device_index = int(match.group(1))
        devices = {device["index"]: device for device in list_input_devices()}
        if device_index not in devices:
            return f"I don't see microphone {device_index}. Say `list microphones` and choose one from the list."
        self.settings["voice_input_device_index"] = device_index
        save_settings(self.settings)
        device = devices[device_index]
        return f"Microphone set to {device_index}: {device['name']}. Try the Voice button again; let us see if this one has a pulse."

    def _test_microphone(self, _match: re.Match[str], _text: str) -> str:
        configured_index = self.settings.get("voice_input_device_index")
        device_index = configured_index if isinstance(configured_index, int) else None
        try:
            result = measure_microphone_level(device_index, seconds=3.0)
        except Exception as exc:
            return f"Microphone test failed: {exc}"

        peak = result["peak"]
        if peak < 250:
            verdict = "That is basically silence. Choose another microphone or check Windows input permissions."
        elif peak < 1800:
            verdict = "I can hear it, but it is quiet. It may work after boosting, but another input may be better."
        else:
            verdict = "Good. That microphone has a healthy signal."
        return f"Tested {get_input_device_label(device_index)}. Peak: {peak}/32767, RMS: {result['rms']}. {verdict}"

    def _auto_select_microphone(self, _match: re.Match[str], _text: str) -> str:
        devices = list_input_devices()
        if not devices:
            return "I couldn't find any microphone input devices."

        best: dict[str, Any] | None = None
        failures: list[str] = []
        for device in devices:
            try:
                result = measure_microphone_level(device["index"], seconds=1.2)
            except Exception as exc:
                failures.append(f"{device['index']}: {exc}")
                continue
            if best is None or result["peak"] > best["peak"]:
                best = result

        if best is None:
            detail = f" Errors: {'; '.join(failures[:3])}" if failures else ""
            return f"I couldn't get a readable test from any microphone.{detail}"

        self.settings["voice_input_device_index"] = int(best["device_index"])
        save_settings(self.settings)
        if best["peak"] < 250:
            return (
                f"The loudest input was {best['device_index']}: {best['device_name']}, but its peak was only "
                f"{best['peak']}/32767. I selected it anyway, though Windows may still be feeding me the wrong mic."
            )
        return (
            f"Selected {best['device_index']}: {best['device_name']} with peak {best['peak']}/32767. "
            "Try the Voice button again; we may finally have a microphone with a heartbeat."
        )

    def _music_settings_status(self, _match: re.Match[str], _text: str) -> str:
        apps = detect_music_apps()
        lines = [
            "Music system status:",
            f"- Preferred app: {self.settings.get('preferred_music_app', 'apple_music')}",
            f"- Provider order: {', '.join(str(item) for item in self.settings.get('music_provider_order', []))}",
            f"- Apple Music installed/running: {'yes' if apps.get('apple_music') else 'no'}",
            f"- Spotify installed/running: {'yes' if apps.get('spotify') else 'no'}",
            f"- YouTube Music fallback: {'on' if apps.get('youtube_music') else 'off'}",
            f"- Apple Music UI automation: {'on' if self.settings.get('apple_music_ui_automation', True) else 'off'}",
            f"- Vision play-button assist: {'on' if self.settings.get('apple_music_use_vision_play_button', True) else 'off'}",
            f"- Click verified result: {'on' if self.settings.get('apple_music_click_first_result', True) else 'off'}",
            f"- Browser fallback: {'on' if self.settings.get('music_open_browser_fallback', True) else 'off'}",
        ]
        return "\n".join(lines)

    def _music_you_pick(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        playlist = pick_playlist_for_window(title, self.settings)
        player = play_playlist(playlist, self.settings.get("preferred_music_app", "spotify"))
        return f"You're in {title}. I'll assume we're being productive. Starting {playlist['label']} via {player}."

    def _media_play_pause(self, _match: re.Match[str], _text: str) -> str:
        press_media_play_pause()
        return "I sent the Windows Play/Pause media key. If Apple Music is focused or has something queued, it should obey. In theory. Windows does enjoy interpretive dance."

    def _request_apple_music_song(self, _match: re.Match[str], _text: str) -> str:
        self.pending_music_request = {"app": "apple_music", "created_at": time.time()}
        return (
            "Yes. Tell me the song or artist, and I will open Apple Music, search for it, "
            "click the first result I can identify, and press Play if Windows lets me."
        )

    def _apple_music_search_command(self, match: re.Match[str], _text: str) -> str:
        query = self._clean_music_query(match.group(1))
        if not query:
            return self._request_apple_music_song(match, _text)
        if self._wants_mobile_music(_text):
            return self._play_mobile_apple_music_query(query)
        if self.settings.get("mobile_music_device_prompt", True) and self.settings.get("mobile_apple_music_enabled", True) and not self._wants_desktop_music(_text):
            self.pending_music_device_request = {"query": query, "created_at": time.time()}
            return f"Should I play '{query}' on this device, or on your mobile device, sir?"
        return self._play_apple_music_query(query)

    def _clean_music_query(self, query: str) -> str:
        return clean_music_query_text(query)

    def _wants_mobile_music(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in ["on my phone", "on phone", "on mobile", "on my iphone", "on iphone", "mobile device"])

    def _wants_desktop_music(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in ["on this device", "on this computer", "on my pc", "on pc", "on my laptop", "on desktop", "on windows"])

    def _play_mobile_apple_music_query(self, query: str) -> str:
        query = self._clean_music_query(query)
        if not query:
            return "Give me a song or artist first, then I can queue it for mobile Apple Music."
        if not self.settings.get("mobile_apple_music_enabled", True):
            return "Mobile Apple Music is disabled in settings. Dramatic, but fixable."
        item = self.phone_queue.enqueue("play_apple_music", {"query": query})
        self.record_action("queue_mobile_apple_music", {"query": query, "id": item.get("id")}, "medium", True, f"Queued mobile Apple Music request for {query}.", verified=True)
        return (
            f"Queued '{query}' for Apple Music on your mobile device. "
            "Run the JARVIS Phone Bridge Shortcut on your iPhone and it will fetch the request. "
            "Tiny relay baton passed, sir."
        )

    def _play_apple_music_query(self, query: str) -> str:
        query = self._clean_music_query(query)
        if not query:
            return "Give me a song, artist, or album to search in Apple Music."
        if self.settings.get("apple_music_ui_automation", True):
            selected_by_ui, message = apple_music_search_and_press_play(query, self.settings)
            if not self.settings.get("apple_music_use_vision_play_button", True):
                if selected_by_ui:
                    return f"{message} I selected the result, but vision play-button assist is off, so I did not verify playback."
                return message
            visual_found, visual_reason, x, y = self.locate_apple_music_play_target(query)
            if visual_found and x is not None and y is not None:
                click_mouse(x, y)
                time.sleep(1.4)
                play_found, play_reason, play_x, play_y = self.locate_apple_music_visible_play_button(query)
                if play_found and play_x is not None and play_y is not None:
                    click_mouse(play_x, play_y)
                    time.sleep(1.5)
                    verified, verify_reason = self.verify_apple_music_playback(query)
                    if verified:
                        return (
                            f"I searched Apple Music for '{query}', selected the matching result, "
                            f"clicked Play, and verified playback. {verify_reason}"
                        )
                    if self.settings.get("auto_press_play_after_music_search", False):
                        press_media_play_pause()
                        time.sleep(1.2)
                        verified_after_key, key_reason = self.verify_apple_music_playback(query)
                        if verified_after_key:
                            return (
                                f"I searched Apple Music for '{query}', clicked the visible Play button, "
                                f"then used the media Play key and verified playback. {key_reason}"
                            )
                    return (
                        f"I searched Apple Music for '{query}' and clicked the visible Play button at {play_x}, {play_y}, "
                        f"but I could not verify that playback started. {verify_reason}"
                    )

                window = _find_apple_music_window(timeout_seconds=2)
                if window is not None and _click_first_apple_music_play_button(window):
                    time.sleep(1.5)
                    verified, verify_reason = self.verify_apple_music_playback(query)
                    if verified:
                        return (
                            f"I searched Apple Music for '{query}', selected the matching result, "
                            f"pressed the visible Play control, and verified playback. {verify_reason}"
                        )
                    return (
                        f"I searched Apple Music for '{query}' and pressed a visible Play control, "
                        f"but I could not verify playback. {verify_reason}"
                    )
                return (
                    f"I searched Apple Music for '{query}', visually identified the matching song target, "
                    f"and clicked it at {x}, {y}, but I could not verify a safe Play button afterward. "
                    f"Selection: {visual_reason} Play check: {play_reason}"
                )
            if selected_by_ui:
                play_found, play_reason, play_x, play_y = self.locate_apple_music_visible_play_button(query)
                if play_found and play_x is not None and play_y is not None:
                    click_mouse(play_x, play_y)
                    time.sleep(1.5)
                    verified, verify_reason = self.verify_apple_music_playback(query)
                    if verified:
                        return f"{message} I then clicked Play and verified playback. {verify_reason}"
                    return f"{message} I clicked Play, but could not verify playback. {verify_reason}"
                return f"{message} I selected the result, but did not find a safe Play button. {play_reason}"
            if "playlist" in message.lower() or "too weak a match" in message.lower() or "verify" in message.lower():
                return f"{message}\nVision check: {visual_reason}"
            return message

        encoded = requests.utils.quote(query)
        launch_allowed_app("apple music", self.settings)
        if self.settings.get("music_open_browser_fallback", True):
            webbrowser.open(f"https://music.apple.com/us/search?term={encoded}")
            return f"I opened Apple Music search for '{query}'. I did not press play because UI automation is disabled."
        return f"I opened Apple Music for '{query}', but browser fallback is disabled and UI automation is off."

    def _volume_control(self, match: re.Match[str], _text: str) -> str:
        direction = (match.group(1) or match.group(2) or "").lower()
        if direction == "unmute":
            direction = "mute"
        set_volume(direction, amount=3)
        if direction == "up":
            return "Volume up. Subtlety was overrated anyway."
        if direction == "down":
            return "Volume down. Your eardrums may send a thank-you note."
        return "Toggled mute."

    def _minimize_window(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        if set_active_window_state("minimize"):
            return f"Minimized: {title}."
        return "I couldn't minimize the active window."

    def _maximize_window(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        if set_active_window_state("maximize"):
            return f"Maximized: {title}."
        return "I couldn't maximize the active window."

    def _restore_window(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        if set_active_window_state("restore"):
            return f"Restored: {title}."
        return "I couldn't restore the active window."

    def _request_close_window(self, _match: re.Match[str], _text: str) -> str:
        title = get_active_window_title()
        self.pending_confirmation = {"action": "close_window", "label": f"closing {title}"}
        return f"Closing the active window can lose unsaved work. Say `confirm` to close: {title}."

    def _request_lock_pc(self, _match: re.Match[str], _text: str) -> str:
        self.pending_confirmation = {"action": "lock_pc", "label": "locking the laptop"}
        return "I can lock the laptop. Say `confirm` and I will secure the kingdom."

    def _set_clipboard(self, match: re.Match[str], _text: str) -> str:
        text = match.group(1).strip().strip("\"'")
        if not text:
            return "Give me text to place on the clipboard."
        if set_windows_clipboard_text(text):
            return f"Copied {len(text)} characters to the clipboard."
        return "I couldn't access the clipboard."

    def _read_clipboard(self, _match: re.Match[str], _text: str) -> str:
        text = get_windows_clipboard_text().strip()
        if not text:
            return "The clipboard is empty, or it contains something other than plain text."
        preview = text[:900] + ("..." if len(text) > 900 else "")
        return f"Clipboard text:\n{preview}"

    def _paste_clipboard(self, _match: re.Match[str], _text: str) -> str:
        if paste_windows_clipboard():
            return "Pasted the clipboard into the active window."
        return "I couldn't send Ctrl+V from here."

    def _type_text(self, match: re.Match[str], _text: str) -> str:
        text = match.group(1).strip().strip("\"'")
        if not text:
            return "Give me text to type."
        if len(text) > 2000:
            return "That is too much text to type safely in one go. Keep it under 2000 characters."
        if not set_windows_clipboard_text(text):
            return "I couldn't place the text on the clipboard, so I did not type it."
        if paste_windows_clipboard():
            return f"Typed {len(text)} characters into the active field."
        return "I copied the text, but could not paste into the active window."

    def _press_key(self, match: re.Match[str], _text: str) -> str:
        key = match.group(1).lower()
        if send_safe_key(key):
            return f"Pressed {key}."
        return f"I couldn't press {key}. Windows may require focus or permission."

    def _mouse_position(self, _match: re.Match[str], _text: str) -> str:
        x, y = mouse_position()
        width, height = screen_size()
        return f"Your mouse is at {x}, {y} on a {width}x{height} screen."

    def _move_mouse_help(self, _match: re.Match[str], _text: str) -> str:
        x, y = move_mouse_relative("right", 80)
        return (
            f"I moved the mouse slightly to {x}, {y}. "
            "For precision, say `move my mouse to center`, `move my mouse left 200`, or `move mouse to 500 300`."
        )

    def _move_mouse_named_position(self, match: re.Match[str], _text: str) -> str:
        name = match.group(1).lower().replace("centre", "center")
        width, height = screen_size()
        positions = {
            "center": (width // 2, height // 2),
            "middle": (width // 2, height // 2),
            "top left": (40, 40),
            "top right": (width - 40, 40),
            "bottom left": (40, height - 40),
            "bottom right": (width - 40, height - 40),
        }
        x, y = positions[name]
        x, y = move_mouse_to(x, y)
        return f"Moved the mouse to {name} at {x}, {y}."

    def _move_mouse_relative(self, match: re.Match[str], _text: str) -> str:
        direction = match.group(1).lower()
        pixels = int(match.group(2) or 120)
        x, y = move_mouse_relative(direction, pixels)
        return f"Moved the mouse {direction} {pixels} pixels to {x}, {y}."

    def _move_mouse(self, match: re.Match[str], _text: str) -> str:
        x, y = move_mouse_to(int(match.group(1)), int(match.group(2)))
        return f"Moved the mouse to {x}, {y}."

    def _click_at(self, match: re.Match[str], _text: str) -> str:
        click_kind = (match.group(1) or "left").lower()
        x = int(match.group(2))
        y = int(match.group(3))
        button = "right" if click_kind == "right" else "left"
        double = click_kind == "double"
        x, y = clamp_screen_point(x, y)
        click_mouse(x, y, button=button, double=double)
        label = "double-clicked" if double else f"{button}-clicked"
        return f"{label.capitalize()} at {x}, {y}."

    def _scroll_mouse(self, match: re.Match[str], _text: str) -> str:
        direction = match.group(1).lower()
        amount = int(match.group(2) or 5)
        scroll_mouse(direction, amount)
        return f"Scrolled {direction}."

    def _list_windows(self, _match: re.Match[str], _text: str) -> str:
        windows = list_visible_windows(limit=12)
        if not windows:
            return "I couldn't find any visible windows."
        lines = ["Visible windows:"]
        for index, window in enumerate(windows, start=1):
            lines.append(f"{index}. {window['title']}")
        return "\n".join(lines)

    def _switch_window(self, match: re.Match[str], _text: str) -> str:
        query = match.group(1).strip().strip(".")
        title = focus_window_by_title(query)
        if title:
            return f"Switched to: {title}."
        return f"I couldn't find a visible window matching '{query}'."

    def _open_known_folder(self, match: re.Match[str], _text: str) -> str:
        folder_name = match.group(1).lower()
        folder = known_folder_path(folder_name)
        if folder is None:
            return f"I don't know the {folder_name} folder."
        folder.mkdir(parents=True, exist_ok=True)
        _launch_path(folder)
        return f"Opened the {folder_name} folder."

    def _create_known_folder(self, match: re.Match[str], _text: str) -> str:
        name = safe_folder_name(match.group(1))
        location_name = match.group(2).lower()
        base = known_folder_path(location_name)
        if base is None:
            return f"I don't know where {location_name} is."
        if not name:
            return "That folder name evaporated after safety cleanup. Choose a more normal name."
        target = base / name
        target.mkdir(parents=True, exist_ok=True)
        _launch_path(target)
        return f"Created and opened {target}."

    def _list_known_folder(self, match: re.Match[str], _text: str) -> str:
        folder_name = match.group(1).lower()
        files = list_known_folder_files(folder_name, limit=12)
        if not files:
            return f"I couldn't find anything in {folder_name}."
        lines = [f"Recent items in {folder_name}:"]
        for index, path in enumerate(files, start=1):
            kind = "folder" if path.is_dir() else "file"
            lines.append(f"{index}. {path.name} ({kind})")
        return "\n".join(lines)

    def _open_recent_file(self, match: re.Match[str], _text: str) -> str:
        folder_name = match.group(1).lower()
        opened = open_recent_file_from_folder(folder_name)
        if opened is None:
            return f"I couldn't find a recent file in {folder_name}."
        return f"Opened the most recent file in {folder_name}: {opened.name}."

    def _system_info(self, _match: re.Match[str], _text: str) -> str:
        snapshot = get_system_snapshot()
        return (
            f"{format_system_snapshot(snapshot)}\n"
            f"Active window: {snapshot.get('active_window', 'Unknown')}\n"
            f"Proactive monitoring: {'on' if self.settings.get('proactive_monitoring_enabled', True) else 'off'}"
        )

    def _set_awareness_mode(self, _match: re.Match[str], text: str) -> str:
        lowered = text.lower()
        enabled = not any(phrase in lowered for phrase in ["off", "disable", "turn off"])
        self.settings["proactive_monitoring_enabled"] = enabled
        save_settings(self.settings)
        if enabled:
            return "Proactive monitoring is on. I shall watch the vitals with tasteful restraint."
        return "Proactive monitoring is off. I will wait politely until summoned."

    def _awareness_status(self, _match: re.Match[str], _text: str) -> str:
        snapshot = get_system_snapshot()
        quiet = current_time_in_quiet_hours(self.settings)
        return (
            f"Monitoring: {'on' if self.settings.get('proactive_monitoring_enabled', True) else 'off'}\n"
            f"Quiet hours active: {'yes' if quiet else 'no'}\n"
            f"{format_system_snapshot(snapshot)}\n"
            f"Current focus: {snapshot.get('active_window', 'Unknown')}"
        )

    def _watch_project_folder(self, match: re.Match[str], _text: str) -> str:
        path_text = match.group(1).strip().strip(".")
        path = normalize_watch_folder(path_text)
        if path is None:
            return f"I could not find that folder: {path_text}"
        folders = [str(normalize_watch_folder(folder) or folder) for folder in self.settings.get("project_watch_folders", [])]
        if str(path) not in folders:
            folders.append(str(path))
        self.settings["project_watch_folders"] = folders
        self.settings["project_watcher_enabled"] = True
        save_settings(self.settings)
        return f"Watching project folder: {path}. I will alert you if changed files start confessing errors."

    def _unwatch_project_folder(self, match: re.Match[str], _text: str) -> str:
        target = match.group(1).strip().strip(".").lower()
        folders = [str(folder) for folder in self.settings.get("project_watch_folders", [])]
        kept = [folder for folder in folders if target not in folder.lower()]
        if len(kept) == len(folders):
            return f"I could not find a watched folder matching '{target}'."
        self.settings["project_watch_folders"] = kept
        save_settings(self.settings)
        return f"Removed {len(folders) - len(kept)} watched folder{'s' if len(folders) - len(kept) != 1 else ''}."

    def _set_project_watcher_mode(self, _match: re.Match[str], text: str) -> str:
        lowered = text.lower()
        enabled = not any(phrase in lowered for phrase in ["off", "disable", "turn off"])
        self.settings["project_watcher_enabled"] = enabled
        save_settings(self.settings)
        if enabled:
            return "Project watcher is on. I will keep an eye on your logs and scripts, tastefully."
        return "Project watcher is off. Your errors may now roam unsupervised."

    def _project_watcher_status(self, _match: re.Match[str], _text: str) -> str:
        folders = [str(folder) for folder in self.settings.get("project_watch_folders", [])]
        lines = [f"Project watcher: {'on' if self.settings.get('project_watcher_enabled', True) else 'off'}"]
        if not folders:
            lines.append("No folders watched yet. Say `watch C:\\path\\to\\project` or use the Watcher button.")
        else:
            lines.append("Watched folders:")
            for index, folder in enumerate(folders, start=1):
                lines.append(f"{index}. {folder}")
        return "\n".join(lines)

    def _open_windows_settings(self, match: re.Match[str], _text: str) -> str:
        requested = match.group(1).lower()
        routes = {
            "wifi": "ms-settings:network-wifi",
            "wi-fi": "ms-settings:network-wifi",
            "bluetooth": "ms-settings:bluetooth",
            "sound": "ms-settings:sound",
            "audio": "ms-settings:sound",
            "display": "ms-settings:display",
            "microphone": "ms-settings:privacy-microphone",
            "privacy": "ms-settings:privacy",
            "apps": "ms-settings:appsfeatures",
            "windows update": "ms-settings:windowsupdate",
        }
        uri = routes.get(requested)
        if not uri:
            return f"I don't have a Windows Settings shortcut for {requested}."
        os.startfile(uri)  # type: ignore[attr-defined]
        return f"Opened {requested} settings."

    def _set_manual_location(self, match: re.Match[str], _text: str) -> str:
        location = match.group(1).strip().strip(".")
        if not location:
            return "Give me a location to save. I remain impressive, not psychic."
        if any(secret in location.lower() for secret in ["password", "api key", "token", "credit card"]):
            return "I will not store private credentials in location settings. Bold attempt, terrible idea."
        self.settings["manual_location"] = location[:300]
        self.settings["location_provider"] = "manual"
        self.settings["location_enabled"] = True
        save_settings(self.settings)
        self.record_action("set_location", {"location": location[:80]}, "medium", True, "Saved manual location.", verified=True)
        return f"Saved your location as {location}. Directions may now proceed with less guessing."

    def _clear_manual_location(self, _match: re.Match[str], _text: str) -> str:
        self.settings["manual_location"] = ""
        self.settings["location_enabled"] = False
        save_settings(self.settings)
        self.record_action("clear_location", {}, "medium", True, "Cleared saved location.", verified=True)
        return "Saved location cleared. I am back to being spatially humble."

    def _enable_startup_location(self, _match: re.Match[str], _text: str) -> str:
        self.settings["auto_update_location_on_startup"] = True
        self.settings["startup_location_provider"] = "ip"
        self.settings["allow_ip_location_lookup"] = True
        self.settings["location_enabled"] = True
        if not str(self.settings.get("manual_location", "")).strip():
            self.settings["location_provider"] = "ip"
        save_settings(self.settings)
        self.record_action("enable_startup_location", {}, "medium", True, "Enabled startup location refresh.", verified=True)
        return "Startup location refresh is enabled. I will update your approximate location when I launch."

    def _disable_startup_location(self, _match: re.Match[str], _text: str) -> str:
        self.settings["auto_update_location_on_startup"] = False
        save_settings(self.settings)
        self.record_action("disable_startup_location", {}, "medium", True, "Disabled startup location refresh.", verified=True)
        return "Startup location refresh is disabled. I will stop updating it on launch."

    def _enable_ip_location(self, _match: re.Match[str], _text: str) -> str:
        self.settings["allow_ip_location_lookup"] = True
        self.settings["location_provider"] = "ip"
        self.settings["location_enabled"] = True
        save_settings(self.settings)
        self.record_action("enable_ip_location", {}, "medium", True, "Enabled approximate IP location lookup.", verified=True)
        return "Approximate IP location is enabled. It is useful for city-level directions, not for finding your chair."

    def _disable_ip_location(self, _match: re.Match[str], _text: str) -> str:
        self.settings["allow_ip_location_lookup"] = False
        if not str(self.settings.get("manual_location", "")).strip():
            self.settings["location_enabled"] = False
        save_settings(self.settings)
        self.record_action("disable_ip_location", {}, "medium", True, "Disabled approximate IP location lookup.", verified=True)
        return "Approximate IP location is disabled. Privacy has reclaimed the room."

    def _location_diagnostics(self, _match: re.Match[str], _text: str) -> str:
        load_environment()
        maps_key_loaded = bool(os.getenv("GOOGLE_MAPS_API_KEY", "").strip())
        manual = str(self.settings.get("manual_location", "")).strip()
        lines = [
            "Location diagnostics:",
            f"- Maps key loaded: {'yes' if maps_key_loaded else 'no'}",
            f"- Startup location refresh: {'on' if self.settings.get('auto_update_location_on_startup', False) else 'off'}",
            f"- IP location lookup: {'allowed' if self.settings.get('allow_ip_location_lookup', False) else 'disabled'}",
            f"- Saved location type: {'coordinates' if looks_like_coordinates(manual) else ('address/place' if manual else 'empty')}",
        ]
        if looks_like_coordinates(manual):
            ok, address, status = reverse_geocode_coordinate_string(manual)
            if ok:
                lines.append(f"- Reverse geocoding: OK, resolved to {address}")
            else:
                lines.append(f"- Reverse geocoding: {status}")
                lines.append("- If the key is loaded, enable the Google Geocoding API and check API restrictions/billing in Google Cloud.")
        return "\n".join(lines)

    def _current_location(self, _match: re.Match[str], _text: str) -> str:
        success, location, message = get_configured_location(self.settings)
        if success:
            if looks_like_coordinates(location):
                return "I only have coordinates right now, not a readable address. Check the location diagnostics, enable the Google Geocoding API, or set your location manually."
            return f"Your approximate location is {location}."
        return f"I do not have a usable location yet. {message}"

    def _directions_from_to(self, match: re.Match[str], _text: str) -> str:
        origin = match.group(1).strip().strip(".")
        destination = match.group(2).strip().strip(".")
        if not origin or not destination:
            return "I need both a start and destination. Directions do prefer having two points."
        mode = normalize_travel_mode(str(self.settings.get("directions_travel_mode", "driving")))
        webbrowser.open(maps_directions_url(origin, destination, mode))
        ok, eta = get_maps_eta(origin, destination, mode)
        eta_line = eta if ok else "Live ETA will be shown in Google Maps."
        self.record_action("open_directions", {"origin": origin[:80], "destination": destination[:80], "mode": mode}, "medium", True, "Opened directions.", verified=True)
        return f"Opened {mode} directions from {origin} to {destination}. {eta_line}"

    def _directions_to_nearby_place(self, match: re.Match[str], _text: str) -> str:
        destination = match.group(1).strip().strip(".")
        return self._brief_nearby_destination(destination)

    def _directions_to(self, match: re.Match[str], _text: str) -> str:
        destination = match.group(1).strip().strip(".")
        return self._open_directions_to_destination(destination)

    def _brief_nearby_destination(self, destination: str) -> str:
        destination = str(destination).strip().strip(".")
        if not destination:
            return "Give me a place to check. Even maps need a noun."
        ok, origin, message = get_configured_location(self.settings)
        if not ok:
            return f"I need a starting location first. {message}"
        mode = normalize_travel_mode(str(self.settings.get("directions_travel_mode", "driving")))
        route_ok, route = get_nearby_route_info(origin, destination, mode)
        resolved_destination = str(route.get("resolved_destination") or destination)
        self.pending_navigation_request = {
            "destination": resolved_destination,
            "label": str(route.get("maps_label") or destination),
            "origin": origin,
            "mode": mode,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        if route_ok:
            place_name = str(route.get("place_name") or destination)
            place_address = str(route.get("place_address") or "").strip()
            place_text = f"{place_name} at {place_address}" if place_address else place_name
            route_summary = str(route.get("route_summary") or "").strip()
            route_line = f" Fastest route: {route_summary}." if route_summary else ""
            return (
                f"The closest {destination} I found is {place_text}. It is about {route['distance']} away, "
                f"roughly {route['duration']} by {mode}.{route_line} Shall I open navigation?"
            )
        return (
            f"I can look for {destination}, but I couldn't get distance and time yet. "
            f"{route.get('error', 'Maps did not return route details.')} Shall I open Maps anyway?"
        )

    def _open_directions_to_destination(self, destination: str, origin: str | None = None, mode: str | None = None) -> str:
        destination = str(destination).strip().strip(".")
        if not destination:
            return "Destination missing. Maps are fussy about that."
        if not origin:
            ok, origin, message = get_configured_location(self.settings)
            if not ok:
                return f"I need a starting location first. {message}"
        mode = normalize_travel_mode(str(mode or self.settings.get("directions_travel_mode", "driving")))
        webbrowser.open(maps_directions_url(origin, destination, mode))
        eta_ok, eta = get_maps_eta(origin, destination, mode)
        eta_line = eta if eta_ok else "Live ETA will be shown in Google Maps."
        self.record_action("open_directions", {"origin": origin[:80], "destination": destination[:80], "mode": mode}, "medium", True, "Opened directions.", verified=True)
        return f"Opened {mode} directions to {destination}. {eta_line}"

    def _eta_to(self, match: re.Match[str], _text: str) -> str:
        destination = match.group(1).strip().strip("? .")
        if not destination:
            return "Tell me where you are going and I will do the dramatic map part."
        ok, origin, message = get_configured_location(self.settings)
        if not ok:
            return f"I need a starting location first. {message}"
        mode = normalize_travel_mode(str(self.settings.get("directions_travel_mode", "driving")))
        eta_ok, eta = get_maps_eta(origin, destination, mode)
        if eta_ok:
            return eta
        webbrowser.open(maps_directions_url(origin, destination, mode))
        self.record_action("open_directions", {"origin": origin[:80], "destination": destination[:80], "mode": mode}, "medium", True, "Opened directions for live ETA.", verified=True)
        return f"I opened Google Maps for the live ETA to {destination}. {eta}"

    def _launch_steam_game(self, match: re.Match[str], _text: str) -> str:
        game_name = match.group(1).strip()
        launched, message = launch_steam_game(game_name, self.settings)
        if launched:
            return f"{message} Try not to blame the frame rate on me."
        return message

    def _import_steam_library(self, _match: re.Match[str], _text: str) -> str:
        added_count, imported = import_steam_library(self.settings)
        if not imported:
            return "I couldn't find installed Steam game manifests. Either Steam is hiding them, or this PC is being needlessly mysterious."
        return f"Imported {len(imported)} installed Steam game{'s' if len(imported) != 1 else ''}. {added_count} were new to my list."

    def _remember_fact(self, match: re.Match[str], _text: str) -> str:
        fact = match.group(1).strip().strip(".")
        return self.save_memory_fact(fact)

    def save_memory_fact(self, fact: str) -> str:
        if not fact:
            return "Give me the thing to remember. I am excellent, not clairvoyant."
        lowered = fact.lower()
        if any(secret_word in lowered for secret_word in ["password", "api key", "secret key", "token", "credit card"]):
            return "I won't store passwords, API keys, tokens, or payment details. Security first, theatrics second."

        memory = {
            "id": f"mem-{int(time.time() * 1000)}",
            "text": fact[:500],
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        self.memories.append(memory)
        self.memories = self.memories[-100:]
        save_memories(self.memories)
        return f"Remembered: {fact}. I have filed it somewhere more reliable than human confidence."

    def _list_memories(self, _match: re.Match[str], _text: str) -> str:
        if not self.memories:
            return "I do not have any saved memories yet. Pristine. Suspiciously so."
        lines = ["Saved memories:"]
        for index, memory in enumerate(self.memories[-20:], start=1):
            lines.append(f"{index}. {memory['text']}")
        return "\n".join(lines)

    def _forget_memory(self, match: re.Match[str], _text: str) -> str:
        target = match.group(1).strip().strip(".").lower()
        if not target:
            return "Tell me what to forget. Preferably not my entire personality."

        kept = []
        removed = []
        for memory in self.memories:
            if target in memory["text"].lower():
                removed.append(memory)
            else:
                kept.append(memory)

        if not removed:
            return f"I couldn't find a saved memory matching '{target}'. Nothing dramatic was deleted."

        self.memories = kept
        save_memories(self.memories)
        return f"Forgot {len(removed)} saved memory item{'s' if len(removed) != 1 else ''} matching '{target}'."

    def _clear_memories(self, _match: re.Match[str], _text: str) -> str:
        self.memories = []
        save_memories(self.memories)
        return "All saved memories cleared. The chat history still was not saved, as requested."

    def _request_empty_recycle_bin(self, _match: re.Match[str], _text: str) -> str:
        self.pending_confirmation = {"action": "empty_recycle_bin", "label": "emptying the Recycle Bin"}
        self.last_risk = "high"
        return "That permanently removes items from the Recycle Bin. I need confirmation first."

    def _play_requested_music(self, match: re.Match[str], text: str) -> str:
        query = clean_music_query_text(match.group(2))
        lowered = text.lower()

        if not query or query.lower() in {"music", "a song", "song", "something"}:
            return "Give me a song, artist, or playlist name and I'll open the closest playable search. I need a target, not vibes in a trench coat."

        encoded = requests.utils.quote(query)
        preferred_app = str(self.settings.get("preferred_music_app", "spotify")).lower()

        if self._wants_mobile_music(text):
            return self._play_mobile_apple_music_query(query)

        if "apple music" in lowered or preferred_app in {"apple_music", "apple music"}:
            if self.settings.get("mobile_music_device_prompt", True) and self.settings.get("mobile_apple_music_enabled", True) and not self._wants_desktop_music(text):
                self.pending_music_device_request = {"query": query, "created_at": time.time()}
                return f"Should I play '{query}' on this device, or on your mobile device, sir?"
            return self._play_apple_music_query(query)

        if "youtube" in lowered or "youtube music" in lowered:
            webbrowser.open(f"https://music.youtube.com/search?q={encoded}")
            return f"I opened YouTube Music search for '{query}'. Autoplay may require you to click the track, because browsers enjoy having boundaries."

        if "spotify" in lowered or preferred_app == "spotify":
            webbrowser.open(f"spotify:search:{encoded}")
            return f"I opened Spotify search for '{query}'. If Spotify focuses the result, one click should finish the ritual."

        webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
        return f"I opened a music search for '{query}'. I did not claim to press play, because unlike some assistants, I have standards."

    def _open_target(self, match: re.Match[str], _text: str) -> str:
        target = match.group(1).strip().lower().rstrip(".")
        if target.startswith("website "):
            target = target.replace("website ", "", 1).strip()

        launched, launch_message = launch_allowed_app(target, self.settings)
        if launched:
            return f"{launch_message} Try to use this power responsibly."

        if target in WEBSITE_SHORTCUTS:
            webbrowser.open(WEBSITE_SHORTCUTS[target])
            return f"Opening {target.title()}."

        if target.startswith(("http://", "https://")):
            webbrowser.open(target)
            return f"Opening {target}."

        if "." in target and " " not in target:
            url = f"https://{target}"
            webbrowser.open(url)
            return f"Opening {url}."

        return launch_message

    def _google_search(self, match: re.Match[str], _text: str) -> str:
        query = match.group(2).strip()
        webbrowser.open(f"https://www.google.com/search?q={requests.utils.quote(query)}")
        return f"Searching Google for '{query}'. The internet has been warned."

    def _youtube_search(self, match: re.Match[str], _text: str) -> str:
        query = match.group(2).strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}")
        return f"Searching YouTube for '{query}'. I hope this remains educational."

    def _time(self, _match: re.Match[str], _text: str) -> str:
        return f"The time is {dt.datetime.now().strftime('%I:%M %p').lstrip('0')}."

    def _date(self, _match: re.Match[str], _text: str) -> str:
        return f"Today is {dt.datetime.now().strftime('%A, %B %d, %Y')}."

    def _battery(self, _match: re.Match[str], _text: str) -> str:
        battery = psutil.sensors_battery()
        if battery is None:
            return "I can't detect a battery. Either this is a desktop, or it has transcended batteries."
        plugged = "plugged in" if battery.power_plugged else "on battery"
        return f"Battery is at {battery.percent:.0f}% and {plugged}."

    def _internet(self, _match: re.Match[str], _text: str) -> str:
        if internet_is_online(timeout=3):
            return "Internet connection looks alive."
        return "Internet connection appears offline. A tragedy in several acts."

    def _screenshot(self, _match: re.Match[str], _text: str) -> str:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        filename = SCREENSHOTS_DIR / f"screenshot_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        image = ImageGrab.grab()
        image.save(filename)
        return f"Screenshot saved to {filename}."

    def _joke(self, _match: re.Match[str], _text: str) -> str:
        return "Why did the developer go broke? Because they used up all their cache. Yes, I am available for weddings."

    def _summarize(self, match: re.Match[str], _text: str) -> str:
        text = match.group(1).strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)
        summary = " ".join(sentences[:2])
        return f"Summary: {summary[:500]}"

    def _todo(self, match: re.Match[str], _text: str) -> str:
        topic = match.group(2).strip()
        return (
            f"To-do list for {topic}:\n"
            "1. Define the goal.\n"
            "2. Break it into the next three visible steps.\n"
            "3. Do the smallest step first.\n"
            "4. Review what changed.\n"
            "5. Pretend this was the plan all along."
        )

    def _focus_timer(self, match: re.Match[str], _text: str) -> str:
        minutes = int(match.group(2) or 25)
        threading.Thread(target=self._timer_thread, args=(minutes,), daemon=True).start()
        return f"Starting a {minutes}-minute focus timer. I shall monitor your heroic attention span."

    def _timer_thread(self, minutes: int) -> None:
        time.sleep(max(1, minutes) * 60)
        messagebox.showinfo("JARVIS", f"Focus timer complete: {minutes} minutes.")


class JarvisApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.assistant = JarvisAssistant()
        self.recognizer = sr.Recognizer()
        self.microphone: sr.Microphone | None = None
        self.voice_backend = "unavailable"
        self._voice_audio_fallback: sr.AudioData | None = None
        self.tts_queue: queue.Queue[str] = queue.Queue()
        self.is_listening = False
        self._tts_stop = threading.Event()
        self._tts_speaking = threading.Event()
        self._tts_process_lock = threading.Lock()
        self._tts_process: subprocess.Popen[str] | None = None
        self._tts_engine: Any | None = None
        self._wake_stop = threading.Event()
        self._wake_pause = threading.Event()
        self._wake_thread: threading.Thread | None = None
        self._wake_followup_until = 0.0
        self._last_spoken_text = ""
        self._last_spoken_at = 0.0
        self._last_tts_error_at = 0.0
        self._tts_failures = 0
        self._tts_cooldown_until = 0.0
        self.boot_frame: ctk.CTkFrame | None = None
        self.boot_canvas: ctk.CTkCanvas | None = None
        self.overlay_window: ctk.CTkToplevel | None = None
        self.overlay_entry: ctk.CTkEntry | None = None
        self.overlay_response_box: ctk.CTkTextbox | None = None
        self.overlay_response_var = ctk.StringVar(value="Ready")
        self.news_panel: ctk.CTkFrame | None = None
        self.news_list_frame: ctk.CTkScrollableFrame | None = None
        self.news_status_var = ctk.StringVar(value="News standing by.")
        self.news_type_var = ctk.StringVar(value="Article")
        self.news_category_var = ctk.StringVar(value="Top Stories")
        self.news_category_menu: ctk.CTkOptionMenu | None = None
        self.news_items: list[dict[str, str]] = []
        self._news_request_id = 0
        self.article_panel: ctk.CTkFrame | None = None
        self.article_title_var = ctk.StringVar(value="Select a headline")
        self.article_meta_var = ctk.StringVar(value="Article reader standing by.")
        self.article_status_var = ctk.StringVar(value="")
        self.article_textbox: ctk.CTkTextbox | None = None
        self.current_article_url = ""
        self.video_news_panel: ctk.CTkFrame | None = None
        self.video_news_list_frame: ctk.CTkScrollableFrame | None = None
        self.video_news_status_var = ctk.StringVar(value="Video newsroom standing by.")
        self.video_news_channel_var = ctk.StringVar(value="Latest")
        self.video_news_items: list[dict[str, str]] = []
        self.video_panel: ctk.CTkFrame | None = None
        self.video_title_var = ctk.StringVar(value="Select a video")
        self.video_meta_var = ctk.StringVar(value="Video viewer standing by.")
        self.video_summary_var = ctk.StringVar(value="")
        self.video_thumbnail_label: ctk.CTkLabel | None = None
        self.video_thumbnail_image: ctk.CTkImage | None = None
        self.current_video_url = ""
        self.video_player_surface: tk.Frame | None = None
        self.video_player_status_var = ctk.StringVar(value="Video player standing by.")
        self.video_player_process: subprocess.Popen[Any] | None = None
        self.video_player_hwnd = 0
        self.video_player_debug_port = 0
        self.video_player_server: http.server.ThreadingHTTPServer | None = None
        self.video_player_server_port = 0
        self.browser_panel: ctk.CTkFrame | None = None
        self.browser_surface: tk.Frame | None = None
        self.browser_address_var = ctk.StringVar(value="")
        self.browser_status_var = ctk.StringVar(value="JARVIS Engine standing by.")
        self.browser_process: subprocess.Popen[Any] | None = None
        self.browser_hwnd = 0
        self.browser_debug_port = 0
        self.browser_home_url = ""
        self._browser_focus_watch_after: str | None = None
        self._browser_mouse_down = False
        self._browser_resize_after: str | None = None
        self._browser_restore_layout: dict[str, float] | None = None
        self.browser_fill_button: ctk.CTkButton | None = None
        self.floating_panels: dict[str, ctk.CTkToplevel] = {}
        self.gesture_points: list[tuple[int, int]] = []
        self.gesture_canvas: ctk.CTkCanvas | None = None
        self.gesture_status_var = ctk.StringVar(value="Webcam gestures are off.")
        self.gesture_window: ctk.CTkToplevel | None = None
        self.gesture_preview_label: ctk.CTkLabel | None = None
        self.gesture_backend_var = ctk.StringVar(value="Backend: checking...")
        self.gesture_mode_var = ctk.StringVar(value=str(self.assistant.settings.get("webcam_gesture_mode", "Safe")))
        self.gesture_enabled_var = ctk.StringVar(value="Off")
        self._gesture_stop = threading.Event()
        self._gesture_thread: threading.Thread | None = None
        self._gesture_capture: Any | None = None
        self._gesture_preview_image: Any | None = None
        self._gesture_wave_positions: list[tuple[float, float]] = []
        self._gesture_open_palm_frames = 0
        self._gesture_last_wave_at = 0.0
        self._gesture_last_click_at = 0.0
        self._gesture_pinched = False
        self._gesture_pinch_frames = 0
        self._gesture_pinch_release_frames = 0
        self._gesture_point_frames = 0
        self._gesture_cursor_samples: list[tuple[float, float]] = []
        self._gesture_last_cursor: tuple[int, int] | None = None
        self.workspace_frame: ctk.CTkFrame | None = None
        self.core_panel: ctk.CTkFrame | None = None
        self.core_body_frame: ctk.CTkFrame | None = None
        self.core_left_telemetry: ctk.CTkFrame | None = None
        self.core_stack_frame: ctk.CTkFrame | None = None
        self.core_right_telemetry: ctk.CTkFrame | None = None
        self._core_compact_layout: bool | None = None
        self.orb: ctk.CTkCanvas | None = None
        self._last_orb_size = 260
        self.chat_panel: ctk.CTkFrame | None = None
        self.side_panel_container: ctk.CTkFrame | None = None
        self.side_panel: ctk.CTkScrollableFrame | None = None
        self.code_panel: ctk.CTkFrame | None = None
        self.code_file_list: ctk.CTkScrollableFrame | None = None
        self.code_preview_box: ctk.CTkTextbox | None = None
        self.code_question_entry: ctk.CTkEntry | None = None
        self.code_search_entry: ctk.CTkEntry | None = None
        self.code_runner_menu: ctk.CTkOptionMenu | None = None
        self.code_runner_lookup: dict[str, str] = {}
        self.code_runner_running = False
        self.code_runner_var = ctk.StringVar(value="No approved runner")
        self.code_apply_button: ctk.CTkButton | None = None
        self.code_discard_button: ctk.CTkButton | None = None
        self.code_pending_edit: dict[str, Any] | None = None
        saved_code_workspace = str(self.assistant.settings.get("coding_workspace_folder", "")).strip()
        self.code_workspace_var = ctk.StringVar(
            value=f"Project: {Path(saved_code_workspace).name}" if saved_code_workspace else "No project selected"
        )
        self.code_selected_path: Path | None = None
        self._drag_panel_offsets: dict[str, tuple[int, int]] = {}
        self._resize_panel_state: dict[str, dict[str, float]] = {}
        self._session_panel_layout: dict[str, dict[str, float]] = json.loads(json.dumps(DEFAULT_DRAGGABLE_PANEL_LAYOUT))
        self._session_panel_visibility = {
            panel: False
            for panel in ["core", "chat", "side", "code", "news", "article", "video_news", "video", "browser"]
        }
        self._layout_autosave_after: str | None = None
        self._layout_autosave_ready = False
        self._panel_layout_dirty = False
        self.mission_running = False
        self.document_review_running = False
        self.boot_step = 0
        self.voice_enabled_var = ctk.BooleanVar(value=bool(self.assistant.settings.get("speak_responses", True)))
        self.wake_enabled_var = ctk.BooleanVar(value=bool(self.assistant.settings.get("wake_listening_enabled", False)))
        self.status_var = ctk.StringVar(value="Online")
        self.window_var = ctk.StringVar(value=get_active_window_title())
        self.time_var = ctk.StringVar(value="")
        self.music_var = ctk.StringVar(value=self._music_status())
        self.mic_var = ctk.StringVar(value="Ready")
        self.command_var = ctk.StringVar(value="Idle")
        self.mode_var = ctk.StringVar(value=self.assistant.current_mode)
        self.permission_mode_var = ctk.StringVar(value=str(self.assistant.settings.get("agent_permission_mode", "Ask for approval")))
        self.vision_var = ctk.StringVar(value="Online" if self.assistant.gemini_client is not None else "Offline")
        self.mouse_var = ctk.StringVar(value=str(self.assistant.settings.get("mouse_control_mode", "Safe")))
        self.last_action_var = ctk.StringVar(value=self.assistant.last_action)
        self.verified_action_var = ctk.StringVar(value=self.assistant.last_verified_action)
        self.risk_var = ctk.StringVar(value=self.assistant.last_risk.title())
        self.awareness_var = ctk.StringVar(value="Starting monitor...")
        self.monitor_summary_var = ctk.StringVar(value="CPU -- | RAM -- | Battery --")
        self.project_watcher_var = ctk.StringVar(value="Project watcher starting...")
        self.health_store = HealthStore(HEALTH_DATA_PATH, int(self.assistant.settings.get("health_data_retention_days", 7)))
        self.health_pairing_token = load_or_create_pairing_token(HEALTH_TOKEN_PATH)
        self.health_bridge: HealthBridgeServer | None = None
        self.health_var = ctk.StringVar(value="Health Bridge starting...")
        self._last_health_alert_at = 0.0
        self.phone_queue = self.assistant.phone_queue
        self.phone_pairing_token = load_or_create_phone_token(PHONE_TOKEN_PATH)
        self.phone_bridge: PhoneBridgeServer | None = None
        self.phone_var = ctk.StringVar(value="Phone Bridge starting...")
        self._monitor_stop = threading.Event()
        self._project_watcher_stop = threading.Event()
        self._last_monitor_alerts: dict[str, float] = {}
        self._last_mode_suggestions: dict[str, float] = {}
        self._last_project_alerts: dict[str, float] = {}
        self._watched_file_state: dict[str, float] = {}
        self._last_online_state: bool | None = None
        self._online_failure_streak = 0
        self._online_success_streak = 0
        self._last_battery_plugged: bool | None = None
        self._active_window_seen_at = time.monotonic()
        self._active_window_last_title = self.window_var.get()
        self._active_window_reminder_sent_for = ""
        self._setup_tts()
        self._setup_ui()
        self._setup_microphone()
        self._setup_hotkey()
        self._schedule_status_updates()
        self._start_awareness_monitor()
        self._start_project_watcher()
        self._start_gemini_model_selection()
        self._start_location_refresh()
        self._start_health_bridge_if_enabled()
        self._start_phone_bridge_if_enabled()
        threading.Thread(target=self._tts_worker, daemon=True).start()
        if self.wake_enabled_var.get():
            self.after(1400, self.start_wake_listener)
        if self.assistant.settings.get("startup_sequence_enabled", True):
            self.after(900, self._run_startup_sequence)

    def _health_context(self) -> dict[str, Any]:
        return {
            "active_window": get_active_window_title(),
            "assistant_mode": self.assistant.current_mode,
            "stated_activity": str(self.assistant.settings.get("health_current_activity", "unspecified")),
        }

    def _start_health_bridge_if_enabled(self) -> None:
        if not integration_enabled(self.assistant.settings, "health_bridge"):
            self.health_var.set("Disabled")
            return
        self.health_store.retention_days = int(self.assistant.settings.get("health_data_retention_days", 7))
        port = int(self.assistant.settings.get("health_bridge_port", 8765))
        self.health_bridge = HealthBridgeServer(
            self.health_store,
            self.health_pairing_token,
            port,
            self._health_context,
            self._on_health_reading_from_bridge,
        )
        status = self.health_bridge.start()
        if status.running:
            self.health_var.set(f"Online: {status.url}")
        else:
            self.health_var.set(status.message)
        self._set_command_status(f"Health bridge {status.message}")

    def _restart_health_bridge(self) -> None:
        if self.health_bridge is not None:
            self.health_bridge.stop()
            self.health_bridge = None
        self._start_health_bridge_if_enabled()

    def _on_health_reading_from_bridge(self, reading: dict[str, Any], assessment: dict[str, str]) -> None:
        self.after(0, lambda r=reading, a=assessment: self._handle_health_reading(r, a))

    def _handle_health_reading(self, reading: dict[str, Any], assessment: dict[str, str]) -> None:
        bpm = reading.get("heart_rate_bpm")
        hrv = reading.get("hrv_ms")
        resting = reading.get("resting_heart_rate_bpm")
        pieces: list[str] = []
        if bpm is not None:
            pieces.append(f"{float(bpm):.0f} BPM")
        if hrv is not None:
            pieces.append(f"HRV {float(hrv):.0f} ms")
        if resting is not None:
            pieces.append(f"Resting {float(resting):.0f} BPM")
        self.health_var.set(" | ".join(pieces) if pieces else "Health update received")
        self.assistant.record_action(
            "health_update",
            {"source": reading.get("source")},
            "safe",
            True,
            assessment.get("summary", "Health update received"),
            verified=True,
        )
        if not self.assistant.settings.get("health_suggestions_enabled", True):
            return
        level = assessment.get("level", "info")
        if level in {"normal", "info"}:
            return
        now = time.monotonic()
        cooldown = max(60, int(self.assistant.settings.get("health_suggestion_cooldown_minutes", 30)) * 60)
        if now - self._last_health_alert_at < cooldown:
            return
        self._last_health_alert_at = now
        message = f"{assessment.get('summary', 'Health update received')} {assessment.get('suggestion', '')}".strip()
        self._emit_awareness_alert(f"health_{level}", message, force=True)

    def _latest_health_status_text(self) -> str:
        bridge_status = self.health_bridge.status() if self.health_bridge is not None else None
        bridge_line = bridge_status.message if bridge_status is not None else "Health bridge is off."
        if bridge_status is not None and bridge_status.running:
            bridge_line = f"Listening at {bridge_status.url}"
        latest = self.health_store.latest()
        if not latest:
            return f"Apple Health Bridge: {bridge_line}\nNo readings received yet. Open Health Setup to pair your iPhone Shortcut."
        parts: list[str] = []
        if latest.get("heart_rate_bpm") is not None:
            parts.append(f"heart rate {float(latest['heart_rate_bpm']):.0f} BPM")
        if latest.get("hrv_ms") is not None:
            parts.append(f"HRV {float(latest['hrv_ms']):.0f} ms")
        if latest.get("resting_heart_rate_bpm") is not None:
            parts.append(f"resting heart rate {float(latest['resting_heart_rate_bpm']):.0f} BPM")
        received = str(latest.get("received_at") or "unknown time")
        activity = str(latest.get("activity") or "unspecified")
        summary = ", ".join(parts) if parts else "health sample received"
        return f"Apple Health Bridge: {bridge_line}\nLatest: {summary}\nActivity: {activity}\nReceived: {received}"

    def _set_health_activity(self, activity: str, source: str = "main") -> None:
        activity = activity.strip()[:80] or "unspecified"
        self.assistant.settings["health_current_activity"] = activity
        self.assistant.settings["health_activity_updated_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        save_settings(self.assistant.settings)
        message = f"Health context set to {activity}. I will use that when interpreting watch readings."
        self._append_chat("System", message)
        self._set_command_status(message)
        if source == "overlay":
            self._set_overlay_response(f"JARVIS: {message}")

    def _copy_to_clipboard(self, value: str, label: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(value)
        self._append_chat("System", f"Copied {label} to clipboard.")

    def _send_test_health_reading(self) -> None:
        try:
            payload = {
                "heart_rate": 82,
                "hrv": 42,
                "activity": self.assistant.settings.get("health_current_activity", "test"),
                "source": "JARVIS test button",
            }
            reading = normalize_health_payload(payload, self._health_context())
            history = self.health_store.readings()
            from health_bridge import assess_health_reading

            assessment = assess_health_reading(reading, history)
            self.health_store.append(reading)
            self._handle_health_reading(reading, assessment)
            self._append_chat("System", "Test health reading accepted. The bridge is alive; delightfully dramatic, but alive.")
        except Exception as exc:
            self._append_chat("System", f"Test health reading failed: {exc}")

    def open_health_bridge_window(self) -> None:
        if self.health_bridge is None and integration_enabled(self.assistant.settings, "health_bridge"):
            self._start_health_bridge_if_enabled()
        status = self.health_bridge.status() if self.health_bridge is not None else None
        url = status.url if status is not None else f"http://127.0.0.1:{int(self.assistant.settings.get('health_bridge_port', 8765))}/health"

        window = ctk.CTkToplevel(self)
        window.title("Apple Health Bridge")
        self._apply_window_icon(window)
        window.geometry("760x680")
        window.minsize(680, 560)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(window, text="Apple Health Bridge", font=ctk.CTkFont(size=22, weight="bold"), text_color="#8be9ff").grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="No Mac required. Your iPhone Shortcut sends Apple Health samples to this PC over your private Wi-Fi.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=700,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        info = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        info.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        info.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(info, text="Shortcut URL", text_color="#8fb7c8").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        url_entry = ctk.CTkEntry(info)
        url_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 6))
        url_entry.insert(0, url)
        ctk.CTkButton(info, text="Copy", width=70, command=lambda: self._copy_to_clipboard(url, "health bridge URL")).grid(row=0, column=2, padx=(0, 12), pady=(12, 6))
        ctk.CTkLabel(info, text="Pairing Code", text_color="#8fb7c8").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        token_entry = ctk.CTkEntry(info, show="*")
        token_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        token_entry.insert(0, self.health_pairing_token)
        ctk.CTkButton(info, text="Copy", width=70, command=lambda: self._copy_to_clipboard(self.health_pairing_token, "health pairing code")).grid(row=1, column=2, padx=(0, 12), pady=6)
        status_text = status.message if status is not None else "Disabled"
        ctk.CTkLabel(info, text=f"Status: {status_text}", text_color="#d9f7ff", anchor="w").grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 12))

        body = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        body.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        instructions = (
            "iPhone Shortcut setup\n"
            "1. On your iPhone, open Shortcuts, tap +, and name it Send Health To JARVIS.\n"
            "2. Add Find Health Samples. Set Type to Heart Rate, Sort by Start Date Latest First, and Limit to 1.\n"
            "3. Add Get Details of Health Samples. Set Detail to Value. This becomes your heart_rate value.\n"
            "4. Add another Get Details of Health Samples. Set Detail to Start Date. This becomes your timestamp value.\n"
            "5. Add Get Contents of URL. Put the Shortcut URL above into the URL field.\n"
            "6. Tap Show More. Set Method to POST and Request Body to JSON.\n"
            "7. In Headers, add X-JARVIS-Health-Token with the Pairing Code above.\n"
            "8. Under Request Body JSON, add two Text rows only.\n"
            "9. Row one: left Key box = heart_rate. Right Text box = the Heart Rate Value from step 3.\n"
            "10. Row two: left Key box = timestamp. Right Text box = the Start Date from step 4.\n"
            "11. Do not add activity or source unless you already know how to type literal text into Shortcuts. JARVIS fills those in automatically.\n"
            "12. Run it once while the iPhone and this PC are on the same Wi-Fi. If Windows asks, allow private-network access.\n\n"
            "If Shortcuts shows the heart rate with units, like 82 count/min, that is fine. JARVIS extracts the number.\n"
            "Optional JSON fields: hrv, resting_heart_rate, activity, source. This is wellness context, not medical diagnosis."
        )
        ctk.CTkLabel(body, text=instructions, text_color="#d9f7ff", justify="left", anchor="nw", wraplength=680).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        status_box = ctk.CTkTextbox(body, height=130, fg_color="#09101d", text_color="#d9f7ff", border_width=1, border_color="#123f5a")
        status_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._write_textbox(status_box, self._latest_health_status_text())

        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Restart Bridge", width=120, command=self._restart_health_bridge).grid(row=0, column=1, padx=5)
        ctk.CTkButton(actions, text="Send Test Reading", width=140, command=self._send_test_health_reading).grid(row=0, column=2, padx=5)
        ctk.CTkButton(
            actions,
            text="Clear Health Data",
            width=140,
            fg_color="#49303a",
            hover_color="#6a3d4b",
            command=lambda: self._clear_health_data(status_box),
        ).grid(row=0, column=3, padx=5)

    def _clear_health_data(self, status_box: ctk.CTkTextbox | None = None) -> None:
        if not messagebox.askyesno("Clear Health Data", "Clear stored local health readings from this PC?"):
            return
        self.health_store.clear()
        self.health_var.set("No readings stored")
        if status_box is not None:
            self._write_textbox(status_box, self._latest_health_status_text())
        self._append_chat("System", "Stored local health readings cleared.")

    def _start_phone_bridge_if_enabled(self) -> None:
        if not integration_enabled(self.assistant.settings, "phone_bridge"):
            self.phone_var.set("Disabled")
            return
        port = int(self.assistant.settings.get("phone_bridge_port", 8766))
        self.phone_bridge = PhoneBridgeServer(self.phone_queue, self.phone_pairing_token, port)
        status = self.phone_bridge.start()
        self.phone_var.set(f"Online: {status.url}" if status.running else status.message)
        self._set_command_status(f"Phone bridge {status.message}")

    def _restart_phone_bridge(self) -> None:
        if self.phone_bridge is not None:
            self.phone_bridge.stop()
            self.phone_bridge = None
        self._start_phone_bridge_if_enabled()

    def _latest_phone_status_text(self) -> str:
        bridge_status = self.phone_bridge.status() if self.phone_bridge is not None else None
        bridge_line = bridge_status.message if bridge_status is not None else "Phone bridge is off."
        if bridge_status is not None and bridge_status.running:
            bridge_line = f"Listening at {bridge_status.url}"
        return f"JARVIS Phone Bridge: {bridge_line}\nPending mobile actions: {self.phone_queue.pending_count()}"

    def open_phone_bridge_window(self) -> None:
        if self.phone_bridge is None and integration_enabled(self.assistant.settings, "phone_bridge"):
            self._start_phone_bridge_if_enabled()
        status = self.phone_bridge.status() if self.phone_bridge is not None else None
        url = status.url if status is not None else f"http://127.0.0.1:{int(self.assistant.settings.get('phone_bridge_port', 8766))}/phone/next"

        window = ctk.CTkToplevel(self)
        window.title("JARVIS Phone Bridge")
        self._apply_window_icon(window)
        window.geometry("760x680")
        window.minsize(680, 560)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(window, text="JARVIS Phone Bridge", font=ctk.CTkFont(size=22, weight="bold"), text_color="#8be9ff").grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="Lets an iPhone Shortcut fetch approved phone-side actions, starting with Apple Music on your mobile device.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=700,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        info = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        info.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        info.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(info, text="Shortcut URL", text_color="#8fb7c8").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        url_entry = ctk.CTkEntry(info)
        url_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=(12, 6))
        url_entry.insert(0, url)
        ctk.CTkButton(info, text="Copy", width=70, command=lambda: self._copy_to_clipboard(url, "phone bridge URL")).grid(row=0, column=2, padx=(0, 12), pady=(12, 6))
        ctk.CTkLabel(info, text="Pairing Code", text_color="#8fb7c8").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        token_entry = ctk.CTkEntry(info, show="*")
        token_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        token_entry.insert(0, self.phone_pairing_token)
        ctk.CTkButton(info, text="Copy", width=70, command=lambda: self._copy_to_clipboard(self.phone_pairing_token, "phone pairing code")).grid(row=1, column=2, padx=(0, 12), pady=6)
        ctk.CTkLabel(info, text=f"Status: {status.message if status is not None else 'Disabled'}", text_color="#d9f7ff", anchor="w").grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 12))

        body = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        body.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        instructions = (
            "iPhone Shortcut setup for mobile Apple Music\n"
            "1. Open Shortcuts on your iPhone, tap +, and name it JARVIS Phone Bridge.\n"
            "2. Add Get Contents of URL. Use the Shortcut URL above.\n"
            "3. Tap Show More. Add header X-JARVIS-Phone-Token with the Pairing Code above.\n"
            "4. Add Get Dictionary Value. Key = action. Dictionary = Contents of URL.\n"
            "5. Add If. Tap the first blue value and choose the Dictionary Value from step 4. Set the condition to is. Type play_apple_music in the last field as plain text.\n"
            "6. Drag the music actions below inside the If block, above Otherwise.\n"
            "7. Inside the If block, add Get Dictionary Value. Key = query. Dictionary = Contents of URL.\n"
            "8. Add Search Apple Music. Search for the query value from step 7.\n"
            "9. Add Get Item from List. Choose First Item.\n"
            "10. Add Play Music using that first item.\n\n"
            "Then ask JARVIS: play Master of Puppets on my phone. The shortcut fetches exactly one queued request."
        )
        ctk.CTkLabel(body, text=instructions, text_color="#d9f7ff", justify="left", anchor="nw", wraplength=680).grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        status_box = ctk.CTkTextbox(body, height=120, fg_color="#09101d", text_color="#d9f7ff", border_width=1, border_color="#123f5a")
        status_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._write_textbox(status_box, self._latest_phone_status_text())

        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Restart Bridge", width=120, command=self._restart_phone_bridge).grid(row=0, column=1, padx=5)
        ctk.CTkButton(actions, text="Queue Test Song", width=130, command=lambda: self._queue_phone_test(status_box)).grid(row=0, column=2, padx=5)
        ctk.CTkButton(actions, text="Clear Queue", width=110, fg_color="#49303a", hover_color="#6a3d4b", command=lambda: self._clear_phone_queue(status_box)).grid(row=0, column=3, padx=5)

    def _queue_phone_test(self, status_box: ctk.CTkTextbox | None = None) -> None:
        self.phone_queue.enqueue("play_apple_music", {"query": "Bad by Michael Jackson"})
        self.phone_var.set(f"Online: queued {self.phone_queue.pending_count()}")
        if status_box is not None:
            self._write_textbox(status_box, self._latest_phone_status_text())
        self._append_chat("System", "Queued a mobile Apple Music test song.")

    def _clear_phone_queue(self, status_box: ctk.CTkTextbox | None = None) -> None:
        self.phone_queue.clear()
        if status_box is not None:
            self._write_textbox(status_box, self._latest_phone_status_text())
        self._append_chat("System", "Phone Bridge queue cleared.")

    def _start_gemini_model_selection(self) -> None:
        if str(self.assistant.settings.get("ai_provider", "gemini")).lower() != "gemini":
            return
        if self.assistant.gemini_client is None:
            return
        self._set_command_status("Checking Gemini models...")
        threading.Thread(target=self._gemini_model_selection_worker, daemon=True).start()

    def _gemini_model_selection_worker(self) -> None:
        self._set_status("Checking models...")
        message = self.assistant.refresh_gemini_model_selection()
        self._append_chat("System", message)
        self._set_status("Online")
        self._set_command_status("Idle")

    def _start_location_refresh(self) -> None:
        if not self.assistant.settings.get("auto_update_location_on_startup", False):
            return
        self._set_command_status("Refreshing location...")
        threading.Thread(target=self._startup_location_worker, daemon=True).start()

    def _startup_location_worker(self) -> None:
        success, message = auto_update_startup_location(self.assistant.settings)

        def deliver() -> None:
            if success:
                self.assistant.record_action("startup_location_refresh", {}, "safe", True, message, verified=True)
                self._append_chat("System", message)
            else:
                self.assistant.record_action("startup_location_refresh", {}, "safe", False, message, verified=True)
                self._append_chat("System", f"Startup location refresh skipped: {message}")
            self._set_command_status("Idle")

        self.after(0, deliver)

    def _run_startup_sequence(self) -> None:
        hour = dt.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 18:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        user_name = str(self.assistant.personality.get("startup_greeting_name") or self.assistant.personality.get("user_name") or "there")
        lines = [
            "Initializing J.A.R.V.I.S.",
            f"Voice system {'online' if self.voice_backend != 'unavailable' else 'offline'}",
            f"Vision system {'online' if self.assistant.gemini_client is not None else 'offline'}",
            f"Mouse control set to {self.assistant.settings.get('mouse_control_mode', 'Safe')} mode",
            f"Gemini connection {'established' if self.assistant.gemini_client is not None else 'unavailable'}",
            f"{greeting}, {user_name}. Systems are ready.",
        ]
        self._set_command_status("Startup diagnostics complete")
        for line in lines:
            self._append_chat("System", line)
        if self.voice_enabled_var.get() and self.assistant.settings.get("startup_greeting_speak", True):
            self.speak(f"{greeting}, {user_name}. Systems are ready.")

    def _setup_tts(self) -> None:
        self.tts_rate = int(self.assistant.settings.get("preferred_voice_speed", 185))
        self.tts_backend = str(self.assistant.settings.get("tts_backend", "windows_sapi")).lower()
        self.tts_voice_id = None
        try:
            engine = pyttsx3.init()
            self._tts_engine = engine
            engine.setProperty("rate", self.tts_rate)
            voices = engine.getProperty("voices")
            preferred_voice = self._find_best_voice(voices)
            self.tts_voice_id = preferred_voice.id if preferred_voice else None
            engine.stop()
        except Exception:
            self.tts_voice_id = None

    def _find_best_voice(self, voices: list[Any]) -> Any | None:
        preferred_terms = self._preferred_voice_terms()
        for term in preferred_terms:
            for voice in voices:
                name = getattr(voice, "name", "").lower()
                voice_id = getattr(voice, "id", "").lower()
                if term in name or term in voice_id:
                    return voice
        return voices[0] if voices else None

    def _preferred_voice_terms(self) -> list[str]:
        terms = self.assistant.settings.get("preferred_tts_voice_terms", DEFAULT_SETTINGS["preferred_tts_voice_terms"])
        return [str(term).lower() for term in terms if str(term).strip()]

    def _setup_ui(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self._apply_window_icon(self)
        saved_geometry = str(self.assistant.settings.get("main_window_geometry", "1240x760"))
        if not re.match(r"^\d{3,4}x\d{3,4}(?:[+-]\d+){0,2}$", saved_geometry):
            saved_geometry = "1240x760"
        self.geometry(saved_geometry)
        self.minsize(1040, 640)
        self.configure(fg_color=UI_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main = ctk.CTkFrame(self, fg_color=UI_BG, corner_radius=0)
        main.grid(row=0, column=0, sticky="nsew", padx=16, pady=(14, 8))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.main_area = main
        command_header = ctk.CTkFrame(main, fg_color=UI_PANEL, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        command_header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        command_header.grid_columnconfigure(0, weight=1)
        title_row = ctk.CTkFrame(command_header, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="w", padx=18, pady=(11, 0))
        ctk.CTkLabel(title_row, text="J.A.R.V.I.S.", font=ctk.CTkFont(size=32, weight="bold"), text_color=UI_TEXT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_row, text="COMMAND CENTER", font=ctk.CTkFont(size=12, weight="bold"), text_color=UI_CYAN).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(8, 0))
        status_pill = ctk.CTkFrame(command_header, fg_color=UI_PANEL_ALT, corner_radius=14, border_width=1, border_color=UI_BORDER)
        status_pill.grid(row=1, column=0, sticky="w", padx=20, pady=(2, 12))
        ctk.CTkLabel(status_pill, text="STATUS", font=ctk.CTkFont(size=10, weight="bold"), text_color=UI_GREEN).grid(row=0, column=0, padx=(12, 6), pady=4)
        status = ctk.CTkLabel(status_pill, textvariable=self.status_var, font=ctk.CTkFont(size=13, weight="bold"), text_color=UI_CYAN)
        status.grid(row=0, column=1, sticky="w", padx=(0, 12), pady=4)
        header_controls = ctk.CTkFrame(command_header, fg_color="transparent")
        header_controls.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 2))
        header_button_style = {"height": 30, "fg_color": UI_CARD, "hover_color": UI_BORDER_SOFT, "text_color": UI_TEXT}
        ctk.CTkButton(header_controls, text="Core", width=64, command=lambda: self._toggle_command_center_panel("core"), **header_button_style).grid(row=0, column=0, padx=4)
        ctk.CTkButton(header_controls, text="Chat", width=64, command=lambda: self._toggle_command_center_panel("chat"), **header_button_style).grid(row=0, column=1, padx=4)
        ctk.CTkButton(header_controls, text="Side", width=64, command=lambda: self._toggle_command_center_panel("side"), **header_button_style).grid(row=0, column=2, padx=4)
        ctk.CTkButton(header_controls, text="Missions", width=86, command=self.open_mission_dashboard_window, **header_button_style).grid(row=0, column=3, padx=4)
        ctk.CTkButton(header_controls, text="Hands", width=84, command=self.open_gesture_pad_window, **header_button_style).grid(row=0, column=4, padx=4)
        ctk.CTkButton(header_controls, text="Layouts", width=76, command=self.open_workspace_layout_window, **header_button_style).grid(row=0, column=5, padx=4)
        ctk.CTkButton(header_controls, text="Panels", width=76, command=self.open_panel_manager_window, **header_button_style).grid(row=0, column=6, padx=(4, 0))
        ctk.CTkButton(header_controls, text="Browser", width=78, command=self.open_browser_panel, **header_button_style).grid(row=0, column=7, padx=(4, 0))

        permission_controls = ctk.CTkFrame(command_header, fg_color="transparent")
        permission_controls.grid(row=1, column=1, sticky="e", padx=18, pady=(0, 10))
        ctk.CTkButton(permission_controls, text="News", width=64, height=30, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=self.open_news_panel).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(permission_controls, text="Videos", width=70, height=30, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=self.open_video_news_panel).grid(row=0, column=1, padx=6)
        ctk.CTkButton(permission_controls, text="Code", width=64, height=30, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._toggle_command_center_panel("code")).grid(row=0, column=2, padx=(6, 10))
        ctk.CTkLabel(permission_controls, text="Permissions", text_color=UI_MUTED).grid(row=0, column=3, padx=(0, 8))
        self.permission_menu = ctk.CTkOptionMenu(
            permission_controls,
            values=list(PERMISSION_MODES),
            variable=self.permission_mode_var,
            command=self._set_permission_mode,
            width=158,
            fg_color=UI_CARD,
            button_color=UI_BORDER,
            button_hover_color="#2898c5",
        )
        self.permission_menu.grid(row=0, column=4)

        workspace = ctk.CTkFrame(main, fg_color=UI_BG, corner_radius=0)
        self.workspace_frame = workspace
        workspace.grid(row=1, column=0, sticky="nsew")
        self.orb = ctk.CTkCanvas(workspace, width=420, height=420, bg=UI_BG, highlightthickness=0)
        self.orb.place(relx=0.5, rely=0.5, anchor="center")
        workspace.bind("<Configure>", self._update_background_orb_layout, add="+")
        self._draw_orb(72)
        self._update_background_orb_layout()

        core_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.core_panel = core_panel
        core_panel.grid_columnconfigure(0, weight=1)
        core_panel.grid_rowconfigure(1, weight=1)

        core_handle = self._panel_drag_handle(core_panel, "CORE")
        core_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        core_body = ctk.CTkScrollableFrame(
            core_panel,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=UI_BORDER_SOFT,
            scrollbar_button_hover_color=UI_BORDER,
        )
        self.core_body_frame = core_body
        core_body.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        core_body.grid_columnconfigure(0, weight=1)
        core_body.grid_columnconfigure(1, weight=0)
        core_body.grid_columnconfigure(2, weight=1)
        core_body.grid_rowconfigure(1, weight=1)

        left_telemetry = ctk.CTkFrame(core_body, fg_color="transparent")
        self.core_left_telemetry = left_telemetry
        left_telemetry.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(16, 8), pady=16)
        left_telemetry.grid_columnconfigure(0, weight=1)
        self._core_status_card(left_telemetry, "ACTIVE WINDOW", self.window_var, 0)
        self._core_status_card(left_telemetry, "MODE", self.mode_var, 1)
        self._core_status_card(left_telemetry, "VISION", self.vision_var, 2)

        core_stack = ctk.CTkFrame(core_body, fg_color="transparent")
        self.core_stack_frame = core_stack
        core_stack.grid(row=0, column=1, rowspan=2, sticky="n", padx=12, pady=(18, 12))
        core_stack.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(core_stack, text="CORE BACKDROP ACTIVE", font=ctk.CTkFont(size=13, weight="bold"), text_color=UI_CYAN).grid(row=0, column=0, pady=(12, 2))
        ctk.CTkLabel(core_stack, textvariable=self.command_var, font=ctk.CTkFont(size=12), text_color=UI_TEXT, wraplength=240).grid(row=1, column=0, pady=(0, 4))

        right_telemetry = ctk.CTkFrame(core_body, fg_color="transparent")
        self.core_right_telemetry = right_telemetry
        right_telemetry.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(8, 16), pady=16)
        right_telemetry.grid_columnconfigure(0, weight=1)
        self._core_status_card(right_telemetry, "MOUSE", self.mouse_var, 0)
        self._core_status_card(right_telemetry, "MUSIC", self.music_var, 1)
        self._core_status_card(right_telemetry, "VITALS", self.monitor_summary_var, 2)
        core_body.bind("<Configure>", self._update_core_responsive_layout)

        chat_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.chat_panel = chat_panel
        chat_panel.grid_columnconfigure(0, weight=1)
        chat_panel.grid_rowconfigure(1, weight=1)
        chat_handle = self._panel_drag_handle(chat_panel, "CHAT")
        chat_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        self.chat_box = ctk.CTkTextbox(chat_panel, wrap="word", font=ctk.CTkFont(size=14), fg_color=UI_PANEL_DEEP, text_color=UI_TEXT, border_width=1, border_color=UI_BORDER_SOFT)
        self.chat_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.chat_box.configure(state="disabled")

        side_container = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.side_panel_container = side_container
        side_container.grid_columnconfigure(0, weight=1)
        side_container.grid_rowconfigure(1, weight=1)
        side_handle = self._panel_drag_handle(side_container, "STATUS")
        side_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        side = ctk.CTkScrollableFrame(
            side_container,
            fg_color=UI_PANEL_ALT,
            corner_radius=8,
            scrollbar_button_color=UI_BORDER_SOFT,
            scrollbar_button_hover_color=UI_BORDER,
        )
        self.side_panel = side
        side.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        side.grid_columnconfigure(0, weight=1)
        self._side_controls(side, 0)
        self._side_label(side, "Active Window", self.window_var, 1)
        self._side_label(side, "Time", self.time_var, 2)
        self._side_label(side, "Mode", self.mode_var, 3)
        self._side_label(side, "Permissions", self.permission_mode_var, 4)
        self._side_label(side, "Vision", self.vision_var, 5)
        self._side_label(side, "Voice", self.mic_var, 6)
        self._side_label(side, "Mouse Control", self.mouse_var, 7)
        self._side_label(side, "Hand Control", self.gesture_enabled_var, 8)
        self._side_label(side, "Music", self.music_var, 9)
        self._side_label(side, "Phone Bridge", self.phone_var, 10)
        self._side_label(side, "Last Action", self.last_action_var, 11)
        self._side_label(side, "Last Verified", self.verified_action_var, 12)
        self._side_label(side, "Risk Level", self.risk_var, 13)
        self._side_label(side, "Command", self.command_var, 14)
        self._side_label(side, "Awareness", self.awareness_var, 15)
        self._side_label(side, "Vitals", self.monitor_summary_var, 16)
        self._side_label(side, "Health", self.health_var, 17)
        self._side_label(side, "Project Watcher", self.project_watcher_var, 18)

        code_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.code_panel = code_panel
        code_panel.grid_columnconfigure(0, weight=1)
        code_panel.grid_rowconfigure(2, weight=1)
        code_handle = self._panel_drag_handle(code_panel, "CODING WORKSPACE")
        code_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        code_toolbar = ctk.CTkFrame(code_panel, fg_color="transparent")
        code_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        code_toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(code_toolbar, textvariable=self.code_workspace_var, anchor="w", text_color=UI_TEXT).grid(row=0, column=0, sticky="ew", padx=(4, 8))
        ctk.CTkButton(code_toolbar, text="Choose Project", width=112, command=self._choose_coding_workspace).grid(row=0, column=1, padx=4)
        self.code_search_entry = ctk.CTkEntry(code_toolbar, placeholder_text="Search files or source...", width=190)
        self.code_search_entry.grid(row=0, column=2, padx=4)
        self.code_search_entry.bind("<Return>", lambda _event: self._refresh_coding_workspace_files())
        ctk.CTkButton(code_toolbar, text="Search", width=74, command=self._refresh_coding_workspace_files).grid(row=0, column=3, padx=(4, 0))
        ctk.CTkButton(code_toolbar, text="Diagnostics", width=92, command=self._run_coding_diagnostics).grid(row=0, column=4, padx=(6, 0))
        ctk.CTkButton(
            code_toolbar,
            text="Hide Panel",
            width=88,
            fg_color=UI_CARD,
            hover_color=UI_BORDER_SOFT,
            command=lambda: self._set_command_center_panel_visible("code", False),
        ).grid(row=0, column=5, padx=(6, 0))
        runner_bar = ctk.CTkFrame(code_toolbar, fg_color="transparent")
        runner_bar.grid(row=1, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        runner_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(runner_bar, text="Approved runner", text_color=UI_MUTED).grid(row=0, column=0, padx=(4, 8))
        self.code_runner_menu = ctk.CTkOptionMenu(runner_bar, values=["No approved runner"], variable=self.code_runner_var, width=230)
        self.code_runner_menu.grid(row=0, column=1, sticky="w")
        ctk.CTkButton(runner_bar, text="Run", width=74, command=self._run_selected_code_runner).grid(row=0, column=2, padx=(8, 0))

        code_body = ctk.CTkFrame(code_panel, fg_color="transparent")
        code_body.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        code_body.grid_columnconfigure(0, weight=0, minsize=210)
        code_body.grid_columnconfigure(1, weight=1)
        code_body.grid_rowconfigure(0, weight=1)
        self.code_file_list = ctk.CTkScrollableFrame(code_body, width=200, fg_color=UI_PANEL_DEEP, corner_radius=8)
        self.code_file_list.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.code_file_list.grid_columnconfigure(0, weight=1)

        code_editor = ctk.CTkFrame(code_body, fg_color=UI_PANEL_DEEP, corner_radius=8)
        code_editor.grid(row=0, column=1, sticky="nsew")
        code_editor.grid_columnconfigure(0, weight=1)
        code_editor.grid_rowconfigure(0, weight=1)
        self.code_preview_box = ctk.CTkTextbox(code_editor, wrap="none", font=ctk.CTkFont(family="Consolas", size=12), fg_color="#050b13", text_color=UI_TEXT)
        self.code_preview_box.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=8, pady=(8, 6))
        self.code_preview_box.insert("1.0", "Choose a project, then select a source file. Proposed edits appear here as a reviewable diff.")
        self.code_preview_box.configure(state="disabled")
        self.code_question_entry = ctk.CTkEntry(code_editor, placeholder_text="Ask for an explanation or describe an edit...")
        self.code_question_entry.grid(row=1, column=0, sticky="ew", padx=(8, 6), pady=(0, 8))
        self.code_question_entry.bind("<Return>", lambda _event: self._explain_selected_code_file())
        ctk.CTkButton(code_editor, text="Explain", width=82, command=self._explain_selected_code_file).grid(row=1, column=1, padx=(0, 8), pady=(0, 6))
        edit_actions = ctk.CTkFrame(code_editor, fg_color="transparent")
        edit_actions.grid(row=2, column=0, columnspan=2, sticky="e", padx=8, pady=(0, 8))
        ctk.CTkButton(edit_actions, text="Propose Edit", width=100, command=self._propose_selected_code_edit).grid(row=0, column=0, padx=3, pady=3)
        self.code_apply_button = ctk.CTkButton(edit_actions, text="Apply", width=72, state="disabled", command=self._apply_pending_code_edit)
        self.code_apply_button.grid(row=0, column=1, padx=4)
        self.code_discard_button = ctk.CTkButton(edit_actions, text="Discard", width=82, state="disabled", fg_color="#49303a", hover_color="#6a3d4b", command=self._discard_pending_code_edit)
        self.code_discard_button.grid(row=1, column=0, padx=3, pady=3)
        ctk.CTkButton(edit_actions, text="Latest Backup", width=118, fg_color="#21465b", hover_color="#2d6886", command=self._preview_latest_code_backup).grid(row=1, column=1, padx=4, pady=3)

        news_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.news_panel = news_panel
        news_panel.grid_columnconfigure(0, weight=1)
        news_panel.grid_rowconfigure(2, weight=1)
        news_handle = self._panel_drag_handle(news_panel, "NEWS")
        news_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        news_toolbar = ctk.CTkFrame(news_panel, fg_color="transparent")
        news_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        news_toolbar.grid_columnconfigure(1, weight=1)
        ctk.CTkSegmentedButton(
            news_toolbar,
            values=["Article", "Video"],
            variable=self.news_type_var,
            command=self._switch_news_type,
            selected_color=UI_BORDER,
            selected_hover_color="#2898c5",
            unselected_color=UI_CARD,
            unselected_hover_color=UI_BORDER_SOFT,
        ).grid(row=0, column=0, sticky="w", padx=(2, 10), pady=4)
        self.news_category_menu = ctk.CTkOptionMenu(
            news_toolbar,
            values=list(DEFAULT_NEWS_FEEDS.keys()),
            variable=self.news_category_var,
            command=lambda _choice: self.refresh_news_panel(),
            width=142,
            fg_color=UI_CARD,
            button_color=UI_BORDER,
            button_hover_color="#2898c5",
        )
        self.news_category_menu.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=4)
        ctk.CTkLabel(news_toolbar, textvariable=self.news_status_var, text_color=UI_TEXT, anchor="w").grid(row=1, column=0, columnspan=2, sticky="ew", padx=(2, 8), pady=4)
        ctk.CTkButton(news_toolbar, text="Refresh", width=82, fg_color=UI_BORDER, hover_color="#2898c5", command=self.refresh_news_panel).grid(row=0, column=2, padx=(6, 4), pady=4)
        ctk.CTkButton(news_toolbar, text="Hide", width=62, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._set_command_center_panel_visible("news", False)).grid(row=0, column=3, padx=(4, 0), pady=4)

        self.news_list_frame = ctk.CTkScrollableFrame(
            news_panel,
            fg_color=UI_PANEL_DEEP,
            corner_radius=8,
            border_width=1,
            border_color=UI_BORDER_SOFT,
            scrollbar_button_color=UI_BORDER_SOFT,
            scrollbar_button_hover_color=UI_BORDER,
        )
        self.news_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.news_list_frame.grid_columnconfigure(0, weight=1)

        article_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.article_panel = article_panel
        article_panel.grid_columnconfigure(0, weight=1)
        article_panel.grid_rowconfigure(3, weight=1)
        article_handle = self._panel_drag_handle(article_panel, "ARTICLE READER")
        article_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        article_toolbar = ctk.CTkFrame(article_panel, fg_color="transparent")
        article_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(7, 3))
        article_toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(article_toolbar, textvariable=self.article_status_var, text_color=UI_GREEN, anchor="w").grid(row=0, column=0, sticky="ew", padx=(2, 8), pady=4)
        ctk.CTkButton(article_toolbar, text="Publisher", width=90, fg_color=UI_BORDER, hover_color="#2898c5", command=self._open_current_article_in_browser).grid(row=0, column=1, padx=4, pady=4)
        ctk.CTkButton(article_toolbar, text="Hide", width=62, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._set_command_center_panel_visible("article", False)).grid(row=0, column=2, padx=(4, 0), pady=4)

        article_heading = ctk.CTkFrame(article_panel, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
        article_heading.grid(row=2, column=0, sticky="ew", padx=10, pady=(3, 7))
        article_heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(article_heading, textvariable=self.article_title_var, text_color=UI_TEXT, anchor="w", justify="left", wraplength=560, font=ctk.CTkFont(size=17, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(article_heading, textvariable=self.article_meta_var, text_color=UI_MUTED, anchor="w", justify="left", wraplength=560).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        self.article_textbox = ctk.CTkTextbox(
            article_panel,
            fg_color=UI_PANEL_DEEP,
            border_width=1,
            border_color=UI_BORDER_SOFT,
            text_color=UI_TEXT,
            wrap="word",
            font=ctk.CTkFont(size=14),
            spacing1=3,
            spacing3=8,
        )
        self.article_textbox.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.article_textbox.insert("1.0", "Choose a headline from the News panel to open it here.")
        self.article_textbox.configure(state="disabled")

        video_news_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.video_news_panel = video_news_panel
        video_news_panel.grid_columnconfigure(0, weight=1)
        video_news_panel.grid_rowconfigure(2, weight=1)
        video_news_handle = self._panel_drag_handle(video_news_panel, "VIDEO NEWS")
        video_news_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))

        video_news_toolbar = ctk.CTkFrame(video_news_panel, fg_color="transparent")
        video_news_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=8)
        video_news_toolbar.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(video_news_toolbar, text="Channel", text_color=UI_MUTED).grid(row=0, column=0, padx=(2, 8), pady=4)
        ctk.CTkOptionMenu(
            video_news_toolbar,
            values=list(DEFAULT_VIDEO_NEWS_FEEDS.keys()),
            variable=self.video_news_channel_var,
            command=lambda _choice: self.refresh_video_news_panel(),
            width=130,
            fg_color=UI_CARD,
            button_color=UI_BORDER,
            button_hover_color="#2898c5",
        ).grid(row=0, column=1, padx=(0, 8), pady=4)
        ctk.CTkLabel(video_news_toolbar, textvariable=self.video_news_status_var, text_color=UI_TEXT, anchor="w").grid(row=0, column=2, sticky="ew", padx=6, pady=4)
        ctk.CTkButton(video_news_toolbar, text="Refresh", width=82, fg_color=UI_BORDER, hover_color="#2898c5", command=self.refresh_video_news_panel).grid(row=0, column=3, padx=4, pady=4)
        ctk.CTkButton(video_news_toolbar, text="Hide", width=62, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._set_command_center_panel_visible("video_news", False)).grid(row=0, column=4, padx=(4, 0), pady=4)

        self.video_news_list_frame = ctk.CTkScrollableFrame(
            video_news_panel,
            fg_color=UI_PANEL_DEEP,
            corner_radius=8,
            border_width=1,
            border_color=UI_BORDER_SOFT,
            scrollbar_button_color=UI_BORDER_SOFT,
            scrollbar_button_hover_color=UI_BORDER,
        )
        self.video_news_list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.video_news_list_frame.grid_columnconfigure(0, weight=1)

        video_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.video_panel = video_panel
        video_panel.grid_columnconfigure(0, weight=1)
        video_panel.grid_rowconfigure(3, weight=1)
        video_handle = self._panel_drag_handle(video_panel, "VIDEO VIEWER")
        video_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        video_toolbar = ctk.CTkFrame(video_panel, fg_color="transparent")
        video_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(7, 3))
        video_toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(video_toolbar, textvariable=self.video_player_status_var, text_color=UI_GREEN, anchor="w").grid(row=0, column=0, sticky="ew", padx=2, pady=4)
        ctk.CTkButton(video_toolbar, text="Play", width=68, fg_color=UI_BORDER, hover_color="#2898c5", command=self._play_current_news_video).grid(row=0, column=1, padx=4, pady=4)
        ctk.CTkButton(video_toolbar, text="External", width=78, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=self._open_current_news_video_external).grid(row=0, column=2, padx=4, pady=4)
        ctk.CTkButton(video_toolbar, text="Hide", width=62, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._set_command_center_panel_visible("video", False)).grid(row=0, column=3, padx=(4, 0), pady=4)
        video_heading = ctk.CTkFrame(video_panel, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
        video_heading.grid(row=2, column=0, sticky="ew", padx=10, pady=(3, 7))
        video_heading.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(video_heading, textvariable=self.video_title_var, text_color=UI_TEXT, anchor="w", justify="left", wraplength=540, font=ctk.CTkFont(size=17, weight="bold")).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        ctk.CTkLabel(video_heading, textvariable=self.video_meta_var, text_color=UI_MUTED, anchor="w", justify="left", wraplength=540).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self.video_player_surface = tk.Frame(video_panel, bg="#000000", highlightthickness=1, highlightbackground=UI_BORDER_SOFT)
        self.video_player_surface.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.video_player_surface.bind("<Configure>", self._resize_embedded_video_player, add="+")
        ctk.CTkLabel(video_panel, textvariable=self.video_summary_var, text_color=UI_MUTED, anchor="w", justify="left", wraplength=620).grid(row=4, column=0, sticky="ew", padx=14, pady=(0, 10))

        browser_panel = ctk.CTkFrame(workspace, fg_color=UI_PANEL_ALT, corner_radius=10, border_width=1, border_color=UI_BORDER_SOFT)
        self.browser_panel = browser_panel
        browser_panel.grid_columnconfigure(0, weight=1)
        browser_panel.grid_rowconfigure(2, weight=1)
        browser_handle = self._panel_drag_handle(browser_panel, "JARVIS ENGINE")
        browser_handle.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        browser_toolbar = ctk.CTkFrame(browser_panel, fg_color="transparent")
        browser_toolbar.grid(row=1, column=0, sticky="ew", padx=10, pady=7)
        browser_toolbar.grid_columnconfigure(4, weight=1)
        browser_button_style = {"width": 54, "height": 30, "fg_color": UI_CARD, "hover_color": UI_BORDER_SOFT}
        ctk.CTkButton(browser_toolbar, text="Back", command=lambda: self._browser_history("back"), **browser_button_style).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkButton(browser_toolbar, text="Next", command=lambda: self._browser_history("forward"), **browser_button_style).grid(row=0, column=1, padx=4)
        ctk.CTkButton(browser_toolbar, text="Home", command=self._browser_home, **browser_button_style).grid(row=0, column=2, padx=4)
        ctk.CTkButton(browser_toolbar, text="Reload", command=self._browser_reload, **browser_button_style).grid(row=0, column=3, padx=4)
        browser_address = ctk.CTkEntry(browser_toolbar, textvariable=self.browser_address_var, placeholder_text="Search with JARVIS Engine or enter an address...", height=32, fg_color=UI_PANEL_DEEP, border_color=UI_BORDER_SOFT)
        browser_address.grid(row=0, column=4, sticky="ew", padx=(6, 4))
        browser_address.bind("<Return>", lambda _event: self._browser_go())
        ctk.CTkButton(browser_toolbar, text="Go", width=48, height=30, fg_color=UI_BORDER, hover_color="#2898c5", command=self._browser_go).grid(row=0, column=5, padx=4)
        ctk.CTkButton(browser_toolbar, text="External", width=72, height=30, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=self._open_browser_external).grid(row=0, column=6, padx=4)
        self.browser_fill_button = ctk.CTkButton(browser_toolbar, text="Fill", width=52, height=30, fg_color=UI_BORDER, hover_color="#2898c5", command=self._toggle_browser_fill)
        self.browser_fill_button.grid(row=0, column=7, padx=4)
        ctk.CTkButton(browser_toolbar, text="Hide", width=54, height=30, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=lambda: self._set_command_center_panel_visible("browser", False)).grid(row=0, column=8, padx=(4, 0))
        ctk.CTkLabel(browser_toolbar, textvariable=self.browser_status_var, text_color=UI_MUTED, anchor="w").grid(row=1, column=0, columnspan=9, sticky="ew", pady=(5, 0))

        self.browser_surface = tk.Frame(browser_panel, bg="#02050a", highlightthickness=1, highlightbackground=UI_BORDER_SOFT)
        self.browser_surface.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.browser_surface.bind("<Configure>", self._resize_embedded_browser, add="+")

        input_frame = ctk.CTkFrame(self, fg_color=UI_PANEL, corner_radius=0)
        input_frame.grid(row=1, column=0, sticky="ew")
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Ask JARVIS anything, or type a command...", height=42, fg_color=UI_PANEL_DEEP, border_color=UI_BORDER_SOFT, text_color=UI_TEXT)
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(18, 8), pady=16)
        self.input_entry.bind("<Return>", lambda _event: self.send_text())

        send_button = ctk.CTkButton(input_frame, text="Send", width=86, fg_color=UI_BORDER, hover_color="#2898c5", command=self.send_text)
        send_button.grid(row=0, column=1, padx=6, pady=16)
        voice_button = ctk.CTkButton(input_frame, text="Voice", width=86, fg_color=UI_CARD, hover_color=UI_BORDER_SOFT, command=self.interrupt_and_listen)
        voice_button.grid(row=0, column=2, padx=6, pady=16)
        voice_toggle = ctk.CTkSwitch(input_frame, text="Speak", variable=self.voice_enabled_var)
        voice_toggle.grid(row=0, column=3, padx=6, pady=16)
        wake_toggle = ctk.CTkSwitch(input_frame, text="Wake", variable=self.wake_enabled_var, command=self._toggle_wake_listener)
        wake_toggle.grid(row=0, column=4, padx=(6, 18), pady=16)

        self._setup_draggable_command_panels()
        self._apply_command_center_visibility()
        self.after(180, self._place_command_panels)
        self.bind("<Configure>", self._on_main_window_configure, add="+")
        self._append_chat("JARVIS", "Online. Text commands are ready; voice is standing by with theatrical restraint.")
        self._show_boot_screen()

    def _coding_workspace_root(self) -> Path | None:
        value = str(self.assistant.settings.get("coding_workspace_folder", "")).strip()
        return normalize_watch_folder(value) if value else None

    def _choose_coding_workspace(self) -> None:
        initial = str(self.assistant.settings.get("coding_workspace_folder", "")).strip()
        path = filedialog.askdirectory(title="Choose coding workspace", initialdir=initial if Path(initial).is_dir() else None)
        root = normalize_watch_folder(path)
        if root is None:
            return
        self.assistant.settings["coding_workspace_folder"] = str(root)
        self.code_workspace_var.set(f"Project: {root.name}")
        self.code_selected_path = None
        self.code_pending_edit = None
        self._set_code_edit_buttons(False)
        save_settings(self.assistant.settings)
        self._set_command_status(f"Coding workspace: {root.name}")
        self._append_chat("System", f"Coding workspace selected: {root}. Read-only analysis is ready.")
        self._refresh_coding_workspace_files()

    def _refresh_coding_workspace_files(self) -> None:
        root = self._coding_workspace_root()
        if root is None:
            self._choose_coding_workspace()
            return
        query = self.code_search_entry.get().strip() if self.code_search_entry is not None else ""
        self._refresh_code_runner_options(root)
        self._set_command_status("Scanning coding workspace...")

        def worker() -> None:
            limit = int(self.assistant.settings.get("coding_workspace_max_files", 800))
            files = coding_workspace_files(root, query=query, limit=limit)
            self.after(0, lambda: self._render_coding_workspace_files(root, files, query))

        threading.Thread(target=worker, daemon=True).start()

    def _render_coding_workspace_files(self, root: Path, files: list[Path], query: str) -> None:
        frame = self.code_file_list
        if frame is None:
            return
        for child in frame.winfo_children():
            child.destroy()
        if not files:
            text = f"No source files matched '{query}'." if query else "No supported source files found."
            ctk.CTkLabel(frame, text=text, anchor="w", justify="left", wraplength=220, text_color="#d9f7ff").grid(row=0, column=0, sticky="ew", padx=8, pady=10)
        else:
            for row, path in enumerate(files):
                relative = str(path.relative_to(root))
                display_name = relative if len(relative) <= 52 else f"...{relative[-49:]}"
                button = ctk.CTkButton(
                    frame,
                    text=display_name,
                    anchor="w",
                    height=30,
                    fg_color=UI_CARD,
                    hover_color=UI_BORDER_SOFT,
                    text_color=UI_TEXT,
                    command=lambda selected=path: self._select_coding_file(selected),
                )
                button.grid(row=row, column=0, sticky="ew", padx=4, pady=2)
        suffix = f" matching '{query}'" if query else ""
        self._set_command_status(f"{len(files)} source files{suffix}")

    def _select_coding_file(self, path: Path) -> None:
        if self.code_pending_edit is not None:
            if self.code_selected_path == path:
                self._append_chat("System", "A proposed edit is still awaiting review. Apply or discard it before replacing the diff preview.")
                return
            self.code_pending_edit = None
            self._set_code_edit_buttons(False)
            self._append_chat("System", "The previous edit proposal was discarded when you selected another file.")
        root = self._coding_workspace_root()
        if root is None:
            return
        safe_path = safe_coding_workspace_file(root, path)
        if safe_path is None:
            self._append_chat("System", "That file is outside the selected coding workspace, so I refused to read it.")
            return
        ok, text = read_coding_file(safe_path)
        self.code_selected_path = safe_path if ok else None
        if self.code_preview_box is not None:
            self.code_preview_box.configure(state="normal")
            self.code_preview_box.delete("1.0", "end")
            self.code_preview_box.insert("1.0", text)
            self.code_preview_box.configure(state="disabled")
            self.code_preview_box.see("1.0")
        relative = str(safe_path.relative_to(root))
        self._set_command_status(f"Reading {relative}" if ok else text)

    def _explain_selected_code_file(self) -> None:
        root = self._coding_workspace_root()
        selected = self.code_selected_path
        if root is None or selected is None:
            self._append_chat("System", "Select a source file in the Coding Workspace first.")
            return
        safe_path = safe_coding_workspace_file(root, selected)
        if safe_path is None:
            self._append_chat("System", "The selected file is no longer available inside the workspace.")
            return
        ok, source = read_coding_file(safe_path)
        if not ok:
            self._append_chat("System", source)
            return
        question = self.code_question_entry.get().strip() if self.code_question_entry is not None else ""
        if self.code_question_entry is not None:
            self.code_question_entry.delete(0, "end")
        relative = str(safe_path.relative_to(root))
        self._set_status("Thinking...")
        self._set_command_status(f"Analyzing {relative}")

        def worker() -> None:
            answer = self.assistant.explain_code_file(relative, source, question)
            def deliver() -> None:
                self._append_chat("JARVIS", f"Code analysis: {relative}\n\n{answer}")
                self._set_overlay_response(f"JARVIS: Code analysis complete for {relative}.")
                self._set_status("Online")
                self._set_command_status(f"Analysis complete: {relative}")
            self.after(0, deliver)

        threading.Thread(target=worker, daemon=True).start()
    def _permission_requires_confirmation(self, risk: str) -> bool:
        if self.assistant.current_mode.lower() == "safe":
            return True
        permission_mode = str(self.assistant.settings.get("agent_permission_mode", "Ask for approval"))
        normalized_risk = risk.lower()
        if permission_mode == "Full access":
            return False
        if permission_mode == "Approve for me":
            return normalized_risk == "high"
        return normalized_risk in {"medium", "high"}

    def _refresh_code_runner_options(self, root: Path | None = None) -> None:
        root = root or self._coding_workspace_root()
        runners = approved_code_runners(root) if root is not None else []
        self.code_runner_lookup = {}
        values: list[str] = []
        for runner in runners:
            display = f"{runner['label']} [{str(runner['risk']).title()}]"
            values.append(display)
            self.code_runner_lookup[display] = str(runner["id"])
        if not values:
            values = ["No approved runner"]
        if self.code_runner_menu is not None:
            self.code_runner_menu.configure(values=values)
        if self.code_runner_var.get() not in values:
            self.code_runner_var.set(values[0])

    def _run_selected_code_runner(self) -> None:
        if self.code_pending_edit is not None:
            self._append_chat("System", "Apply or discard the pending code edit before replacing its diff with runner output.")
            return
        if self.code_runner_running:
            self._append_chat("System", "A code runner is already active. One controlled explosion at a time.")
            return
        root = self._coding_workspace_root()
        if root is None:
            self._choose_coding_workspace()
            return
        display = self.code_runner_var.get()
        runner_id = self.code_runner_lookup.get(display)
        runner = next((item for item in approved_code_runners(root) if item["id"] == runner_id), None)
        if runner is None or runner_id is None:
            self._append_chat("System", "No approved runner is available for this project.")
            return
        risk = str(runner.get("risk", "high"))
        if self._permission_requires_confirmation(risk) and not messagebox.askyesno(
            "Confirm Code Runner",
            f"Run {runner['label']} in {root.name}?\n\nProject tests can execute project code. Secret-like environment variables are removed, but the runner can still read files inside this workspace.",
            parent=self,
        ):
            self._set_command_status("Code runner cancelled")
            return
        self.code_runner_running = True
        self._set_status("Acting...")
        self._set_command_status(f"Running {runner['label']}...")

        def worker() -> None:
            result = run_approved_code_runner(root, runner_id, timeout_seconds=120)
            def deliver() -> None:
                self.code_runner_running = False
                output = str(result.get("output", "No output."))
                header = (
                    f"RUNNER: {result.get('label', runner_id)}\n"
                    f"RESULT: {'PASS' if result.get('ok') else 'FAIL'}\n"
                    f"EXIT CODE: {result.get('returncode')}\n"
                    f"DURATION: {result.get('duration', 0)} seconds\n\n"
                )
                if self.code_preview_box is not None:
                    self.code_preview_box.configure(state="normal")
                    self.code_preview_box.delete("1.0", "end")
                    self.code_preview_box.insert("1.0", header + output)
                    self.code_preview_box.configure(state="disabled")
                    self.code_preview_box.see("1.0")
                success = bool(result.get("ok"))
                message = f"{result.get('label', runner_id)} {'passed' if success else 'failed'} in {result.get('duration', 0)} seconds."
                self.assistant.record_action("run_code_check", {"project": str(root), "runner": runner_id}, risk, success, message, verified=True)
                self._append_chat("JARVIS", message)
                self._set_status("Online")
                self._set_command_status(message)
            self.after(0, deliver)

        threading.Thread(target=worker, daemon=True).start()
    def _run_coding_diagnostics(self) -> None:
        if self.code_pending_edit is not None:
            self._append_chat("System", "Apply or discard the pending code edit before replacing its diff with diagnostics.")
            self._set_command_status("Code edit still awaiting review")
            return
        root = self._coding_workspace_root()
        if root is None:
            self._choose_coding_workspace()
            return
        self._set_status("Thinking...")
        self._set_command_status("Running local project diagnostics...")

        def worker() -> None:
            limit = int(self.assistant.settings.get("coding_workspace_max_files", 800))
            report = diagnose_coding_workspace(root, limit=limit)
            output = format_coding_diagnostics(report)
            def deliver() -> None:
                if self.code_preview_box is not None:
                    self.code_preview_box.configure(state="normal")
                    self.code_preview_box.delete("1.0", "end")
                    self.code_preview_box.insert("1.0", output)
                    self.code_preview_box.configure(state="disabled")
                    self.code_preview_box.see("1.0")
                issue_count = len(report.get("issues", []))
                self.assistant.last_action = "Code diagnostics"
                self.assistant.last_risk = "safe"
                self.assistant.record_action("diagnose_code_project", {"project": str(root)}, "safe", True, f"Scanned {report.get('file_count', 0)} files; found {issue_count} issues.", verified=True)
                self._append_chat("JARVIS", f"Diagnostics complete for {root.name}. I scanned {report.get('file_count', 0)} source files and found {issue_count} issue{'s' if issue_count != 1 else ''} in the supported checks.")
                self._set_status("Online")
                self._set_command_status(f"Diagnostics complete: {issue_count} issues")
            self.after(0, deliver)

        threading.Thread(target=worker, daemon=True).start()
    def _set_code_edit_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        if self.code_apply_button is not None:
            self.code_apply_button.configure(state=state)
        if self.code_discard_button is not None:
            self.code_discard_button.configure(state=state)

    def _propose_selected_code_edit(self) -> None:
        root = self._coding_workspace_root()
        selected = self.code_selected_path
        if root is None or selected is None:
            self._append_chat("System", "Select a source file before requesting an edit.")
            return
        safe_path = safe_coding_workspace_file(root, selected)
        if safe_path is None:
            self._append_chat("System", "The selected file is no longer safely inside the coding workspace.")
            return
        request = self.code_question_entry.get().strip() if self.code_question_entry is not None else ""
        if not request:
            self._append_chat("System", "Describe the code change in the question box first.")
            return
        try:
            original_bytes = safe_path.read_bytes()
            original_text = original_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._append_chat("System", f"I could not prepare that UTF-8 source file for editing: {exc}")
            return
        if self.code_question_entry is not None:
            self.code_question_entry.delete(0, "end")
        self.code_pending_edit = None
        self._set_code_edit_buttons(False)
        relative = str(safe_path.relative_to(root))
        self._set_status("Thinking...")
        self._set_command_status(f"Preparing edit for {relative}")

        def worker() -> None:
            proposal = self.assistant.propose_code_edit(relative, original_text, request)
            def deliver() -> None:
                self._set_status("Online")
                if not proposal.get("ok"):
                    error = str(proposal.get("error", "The edit proposal failed."))
                    self._append_chat("System", error)
                    self._set_command_status("Edit proposal failed")
                    return
                normalized_original = original_text.replace("\r\n", "\n").replace("\r", "\n")
                updated = str(proposal["updated_content"])
                diff_lines = list(
                    difflib.unified_diff(
                        normalized_original.splitlines(),
                        updated.splitlines(),
                        fromfile=relative,
                        tofile=f"{relative} (proposed)",
                        lineterm="",
                        n=4,
                    )
                )
                if not diff_lines:
                    self._append_chat("System", "The proposal produced no visible changes, so I discarded it.")
                    return
                diff_text = "\n".join(diff_lines)
                self.code_pending_edit = {
                    "root": str(root),
                    "path": str(safe_path),
                    "relative": relative,
                    "summary": str(proposal.get("summary", "Proposed code update.")),
                    "updated_content": updated,
                    "original_hash": hashlib.sha256(original_bytes).hexdigest(),
                    "newline": "\r\n" if b"\r\n" in original_bytes else "\n",
                }
                display = diff_text if len(diff_text) <= 120000 else diff_text[:120000] + "\n\n[Diff preview truncated]"
                if self.code_preview_box is not None:
                    self.code_preview_box.configure(state="normal")
                    self.code_preview_box.delete("1.0", "end")
                    self.code_preview_box.insert("1.0", display)
                    self.code_preview_box.configure(state="disabled")
                    self.code_preview_box.see("1.0")
                self._set_code_edit_buttons(True)
                summary = str(self.code_pending_edit["summary"])
                self._append_chat("JARVIS", f"Edit proposed for {relative}: {summary}\nReview the diff, then choose Apply or Discard.")
                self._set_command_status(f"Edit ready for review: {relative}")
            self.after(0, deliver)

        threading.Thread(target=worker, daemon=True).start()

    def _preview_latest_code_backup(self) -> None:
        if self.code_pending_edit is not None:
            self._append_chat("System", "Apply or discard the current proposal before previewing a backup.")
            return
        root = self._coding_workspace_root()
        selected = self.code_selected_path
        if root is None or selected is None:
            self._append_chat("System", "Select a source file before looking for its backups.")
            return
        safe_path = safe_coding_workspace_file(root, selected)
        if safe_path is None:
            self._append_chat("System", "The selected file is no longer safely inside the workspace.")
            return
        backup_root = root / ".jarvis_backups"
        if not backup_root.exists() or backup_root.is_symlink():
            self._append_chat("System", "No safe JARVIS backup folder exists for this file.")
            return
        backup_base = backup_root / safe_path.relative_to(root)
        if not backup_base.parent.exists():
            self._append_chat("System", "No JARVIS backup exists for this file yet.")
            return
        candidates: list[Path] = []
        for item in backup_base.parent.glob(f"{backup_base.name}.*.bak"):
            try:
                item.resolve().relative_to(backup_root.resolve())
                if item.is_file() and not item.is_symlink():
                    candidates.append(item)
            except (OSError, ValueError):
                continue
        candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            self._append_chat("System", "No JARVIS backup exists for this file yet.")
            return
        backup_path = candidates[0]
        try:
            current_bytes = safe_path.read_bytes()
            current_text = current_bytes.decode("utf-8")
            backup_text = backup_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._append_chat("System", f"I could not read that backup safely: {exc}")
            return
        normalized_current = current_text.replace("\r\n", "\n").replace("\r", "\n")
        normalized_backup = backup_text.replace("\r\n", "\n").replace("\r", "\n")
        if normalized_current == normalized_backup:
            self._append_chat("System", "The latest backup is identical to the current file.")
            return
        relative = str(safe_path.relative_to(root))
        diff_text = "\n".join(
            difflib.unified_diff(
                normalized_current.splitlines(),
                normalized_backup.splitlines(),
                fromfile=relative,
                tofile=f"{relative} (restore {backup_path.name})",
                lineterm="",
                n=4,
            )
        )
        self.code_pending_edit = {
            "root": str(root),
            "path": str(safe_path),
            "relative": relative,
            "summary": f"Restore backup {backup_path.name}",
            "updated_content": normalized_backup,
            "original_hash": hashlib.sha256(current_bytes).hexdigest(),
            "newline": "\r\n" if b"\r\n" in current_bytes else "\n",
        }
        if self.code_preview_box is not None:
            self.code_preview_box.configure(state="normal")
            self.code_preview_box.delete("1.0", "end")
            self.code_preview_box.insert("1.0", diff_text[:120000] + ("\n\n[Diff preview truncated]" if len(diff_text) > 120000 else ""))
            self.code_preview_box.configure(state="disabled")
            self.code_preview_box.see("1.0")
        self._set_code_edit_buttons(True)
        self._append_chat("JARVIS", f"Latest backup prepared for {relative}. Review the restoration diff, then choose Apply or Discard.")
        self._set_command_status(f"Backup ready for review: {relative}")
    def _discard_pending_code_edit(self, announce: bool = True) -> None:
        had_proposal = self.code_pending_edit is not None
        self.code_pending_edit = None
        self._set_code_edit_buttons(False)
        if self.code_selected_path is not None:
            self._select_coding_file(self.code_selected_path)
        if announce and had_proposal:
            self._append_chat("System", "Proposed code edit discarded. No files were changed.")
            self._set_command_status("Code edit discarded")

    def _apply_pending_code_edit(self) -> None:
        pending = self.code_pending_edit
        if not isinstance(pending, dict):
            self._append_chat("System", "There is no reviewed code edit waiting to be applied.")
            return
        needs_confirmation = self._permission_requires_confirmation("medium")

        relative = str(pending.get("relative", "selected file"))
        if needs_confirmation and not messagebox.askyesno(
            "Confirm Code Edit",
            f"Apply the reviewed edit to {relative}?\n\nA timestamped backup will be created first.",
            parent=self,
        ):
            self._set_command_status("Code edit awaiting approval")
            return

        root = normalize_watch_folder(str(pending.get("root", "")))
        path = Path(str(pending.get("path", "")))
        safe_path = safe_coding_workspace_file(root, path) if root is not None else None
        if root is None or safe_path is None:
            self._append_chat("System", "The target file is no longer safely inside the selected workspace.")
            self._discard_pending_code_edit(announce=False)
            return
        success, result_message, backup_path = apply_code_edit_with_backup(
            root,
            safe_path,
            str(pending.get("updated_content", "")),
            str(pending.get("original_hash", "")),
            str(pending.get("newline", "\n")),
        )
        if not success or backup_path is None:
            if "changed after" in result_message.lower():
                result_message += " I refused to overwrite the newer version; request a fresh edit."
                self._discard_pending_code_edit(announce=False)
            self._append_chat("System", result_message)
            self._set_command_status("Code edit failed")
            return

        summary = str(pending.get("summary", "Code update applied."))
        self.code_pending_edit = None
        self._set_code_edit_buttons(False)
        self._select_coding_file(safe_path)
        message = f"Applied edit to {relative}. Backup: {backup_path}. {summary}"
        self.assistant.record_action("edit_code_file", {"file": relative, "backup": str(backup_path)}, "medium", True, message, verified=True)
        self._append_chat("JARVIS", f"Task complete. Updated {relative}. A backup was saved before the change.")
        self._set_command_status(f"Edit applied: {relative}")
    def _update_core_responsive_layout(self, _event: Any | None = None) -> None:
        body = self.core_body_frame
        left = self.core_left_telemetry
        stack = self.core_stack_frame
        right = self.core_right_telemetry
        if body is None or left is None or stack is None or right is None:
            return

        width = max(body.winfo_width(), 1)
        height = max(body.winfo_height(), 1)
        compact = width < 780
        if compact != self._core_compact_layout:
            for child in (left, stack, right):
                child.grid_forget()
            for row in range(5):
                body.grid_rowconfigure(row, weight=0)
            for column in range(3):
                body.grid_columnconfigure(column, weight=0)

            if compact:
                body.grid_columnconfigure(0, weight=1)
                body.grid_rowconfigure(0, weight=1)
                body.grid_rowconfigure(1, weight=0)
                body.grid_rowconfigure(2, weight=1)
                left.grid(row=0, column=0, sticky="nsew", padx=12, pady=(10, 4))
                stack.grid(row=1, column=0, sticky="n", padx=12, pady=4)
                right.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 10))
            else:
                body.grid_columnconfigure(0, weight=1)
                body.grid_columnconfigure(1, weight=0)
                body.grid_columnconfigure(2, weight=1)
                body.grid_rowconfigure(1, weight=1)
                left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(16, 8), pady=16)
                stack.grid(row=0, column=1, rowspan=2, sticky="n", padx=12, pady=(18, 12))
                right.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(8, 16), pady=16)
            self._core_compact_layout = compact

    def _update_background_orb_layout(self, _event: Any | None = None) -> None:
        workspace = self.workspace_frame
        if workspace is None or self.orb is None:
            return
        width = max(workspace.winfo_width(), 1)
        height = max(workspace.winfo_height(), 1)
        target_size = max(260, min(560, int(min(width, height) * 0.72)))
        if abs(target_size - self._last_orb_size) >= 8:
            self._last_orb_size = int(target_size)
            self.orb.configure(width=int(target_size), height=int(target_size))
        self.orb.place(relx=0.5, rely=0.5, anchor="center")
        try:
            self.orb.lower()
        except Exception:
            pass

    def _enable_layout_autosave(self) -> None:
        self._place_command_panels()
        self._update_background_orb_layout()
        self.update_idletasks()
        self._layout_autosave_ready = True
        self._schedule_layout_autosave()

    def _on_main_window_configure(self, event: Any) -> None:
        if event.widget is self and self._layout_autosave_ready:
            self._schedule_layout_autosave()

    def _schedule_layout_autosave(self, panel_change: bool = False) -> None:
        if not self._layout_autosave_ready:
            return
        if panel_change:
            self._panel_layout_dirty = True
        if self._layout_autosave_after is not None:
            try:
                self.after_cancel(self._layout_autosave_after)
            except Exception:
                pass
        self._layout_autosave_after = self.after(450, self._save_ui_layout_now)

    def _save_ui_layout_now(self) -> None:
        self._layout_autosave_after = None
        if not self._layout_autosave_ready:
            return
        try:
            geometry = self.geometry()
            if re.match(r"^\d{3,4}x\d{3,4}(?:[+-]\d+){2}$", geometry):
                self.assistant.settings["main_window_geometry"] = geometry
            save_settings(self.assistant.settings)
        except Exception:
            pass
    def _panel_drag_handle(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        handle = ctk.CTkFrame(parent, fg_color=UI_PANEL, corner_radius=8, height=36, border_width=1, border_color=UI_BORDER_SOFT)
        handle.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            handle,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=UI_CYAN,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(handle, text="DRAG", font=ctk.CTkFont(size=10, weight="bold"), text_color=UI_MUTED).grid(row=0, column=1, padx=(8, 4))
        ctk.CTkLabel(handle, text=":::",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color=UI_BLUE).grid(row=0, column=2, padx=(0, 12))
        return handle

    def _panel_widget(self, panel: str) -> Any | None:
        if panel == "core":
            return self.core_panel
        if panel == "chat":
            return self.chat_panel
        if panel == "side":
            return self.side_panel_container
        if panel == "code":
            return self.code_panel
        if panel == "news":
            return self.news_panel
        if panel == "article":
            return self.article_panel
        if panel == "video_news":
            return self.video_news_panel
        if panel == "video":
            return self.video_panel
        if panel == "browser":
            return self.browser_panel
        return None

    def _panel_layout(self, panel: str) -> dict[str, float]:
        rect = self._session_panel_layout.get(panel)
        if not isinstance(rect, dict):
            rect = DEFAULT_DRAGGABLE_PANEL_LAYOUT.get(panel, {}).copy()
        default_rect = DEFAULT_DRAGGABLE_PANEL_LAYOUT.get(panel, {})
        return {
            "relx": float(rect.get("relx", default_rect.get("relx", 0.0))),
            "rely": float(rect.get("rely", default_rect.get("rely", 0.0))),
            "relw": max(0.18, float(rect.get("relw", default_rect.get("relw", 0.3)))),
            "relh": max(0.18, float(rect.get("relh", default_rect.get("relh", 0.3)))),
        }

    def _setup_draggable_command_panels(self) -> None:
        panels = [
            ("core", self.core_panel),
            ("chat", self.chat_panel),
            ("side", self.side_panel_container),
            ("code", self.code_panel),
            ("news", self.news_panel),
            ("article", self.article_panel),
            ("video_news", self.video_news_panel),
            ("video", self.video_panel),
            ("browser", self.browser_panel),
        ]
        for key, panel in panels:
            if panel is None:
                continue
            handle = panel.winfo_children()[0] if panel.winfo_children() else panel
            for widget in [handle, *handle.winfo_children()]:
                widget.bind("<ButtonPress-1>", lambda event, item=key: self._start_panel_drag(item, event))
                widget.bind("<B1-Motion>", lambda event, item=key: self._drag_command_panel(item, event))
                widget.bind("<ButtonRelease-1>", lambda event, item=key: self._finish_panel_drag(item, event))
            self._add_panel_resize_grip(key, panel)
        self._place_command_panels()

    def _add_panel_resize_grip(self, panel: str, widget: ctk.CTkFrame) -> None:
        grip = ctk.CTkFrame(widget, width=20, height=20, fg_color=UI_CARD, corner_radius=5, border_width=1, border_color=UI_BLUE)
        grip.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)
        grip.grid_propagate(False)
        ctk.CTkLabel(grip, text="<>", font=ctk.CTkFont(size=9, weight="bold"), text_color=UI_CYAN).place(relx=0.5, rely=0.5, anchor="center")
        for target in [grip, *grip.winfo_children()]:
            target.bind("<ButtonPress-1>", lambda event, item=panel: self._start_panel_resize(item, event))
            target.bind("<B1-Motion>", lambda event, item=panel: self._resize_command_panel(item, event))
            target.bind("<ButtonRelease-1>", lambda event, item=panel: self._finish_panel_resize(item, event))

    def _place_command_panels(self) -> None:
        for panel in ["core", "chat", "side", "code", "news", "article", "video_news", "video", "browser"]:
            if self._session_panel_visibility.get(panel, False):
                self._place_command_panel(panel)

    def _place_command_panel(self, panel: str) -> None:
        widget = self._panel_widget(panel)
        if widget is None:
            return
        rect = self._panel_layout(panel)
        min_w, min_h = self._minimum_panel_size(panel)
        max_w_ratio, max_h_ratio = self._maximum_panel_size_ratio(panel)
        parent_w = max(self.workspace_frame.winfo_width() if self.workspace_frame else 1, 1)
        parent_h = max(self.workspace_frame.winfo_height() if self.workspace_frame else 1, 1)
        min_relw = min(0.98, min_w / parent_w) if parent_w > 20 else 0.18
        min_relh = min(0.98, min_h / parent_h) if parent_h > 20 else 0.18
        max_relw = max(min_relw, min(0.98, max_w_ratio))
        max_relh = max(min_relh, min(0.98, max_h_ratio))
        relw = max(min_relw, min(max_relw, rect["relw"]))
        relh = max(min_relh, min(max_relh, rect["relh"]))
        relx = max(0.0, min(1.0 - relw, rect["relx"]))
        rely = max(0.0, min(1.0 - relh, rect["rely"]))
        widget.place(
            relx=relx,
            rely=rely,
            relwidth=relw,
            relheight=relh,
        )
        widget.lift()
        self._update_background_orb_layout()

    def _start_panel_drag(self, panel: str, event: Any) -> None:
        widget = self._panel_widget(panel)
        if widget is None or self.workspace_frame is None:
            return
        self._drag_panel_offsets[panel] = (event.x_root - widget.winfo_rootx(), event.y_root - widget.winfo_rooty())
        widget.lift()
        self._set_command_status(f"Moving {panel.title()} panel")

    def _drag_command_panel(self, panel: str, event: Any) -> None:
        widget = self._panel_widget(panel)
        parent = self.workspace_frame
        if widget is None or parent is None:
            return
        offset_x, offset_y = self._drag_panel_offsets.get(panel, (0, 0))
        parent_w = max(parent.winfo_width(), 1)
        parent_h = max(parent.winfo_height(), 1)
        min_w, min_h = self._minimum_panel_size(panel)
        max_w_ratio, max_h_ratio = self._maximum_panel_size_ratio(panel)
        max_w = max(min_w, int(parent_w * max_w_ratio))
        max_h = max(min_h, int(parent_h * max_h_ratio))
        widget_w = min(max_w, max(widget.winfo_width(), 80))
        widget_h = min(max_h, max(widget.winfo_height(), 80))
        x = event.x_root - parent.winfo_rootx() - offset_x
        y = event.y_root - parent.winfo_rooty() - offset_y
        x = max(0, min(max(parent_w - min_w, 0), x))
        y = max(0, min(max(parent_h - min_h, 0), y))
        rect = self._panel_layout(panel)
        widget.place(
            relx=x / parent_w,
            rely=y / parent_h,
            relwidth=max(0.18, widget_w / parent_w if widget_w else rect["relw"]),
            relheight=max(0.18, widget_h / parent_h if widget_h else rect["relh"]),
        )
        self._schedule_layout_autosave(panel_change=True)

    def _finish_panel_drag(self, panel: str, _event: Any) -> None:
        widget = self._panel_widget(panel)
        parent = self.workspace_frame
        if widget is None or parent is None:
            return
        parent_w = max(parent.winfo_width(), 1)
        parent_h = max(parent.winfo_height(), 1)
        self._session_panel_layout[panel] = {
            "relx": round(max(0.0, widget.winfo_x() / parent_w), 4),
            "rely": round(max(0.0, widget.winfo_y() / parent_h), 4),
            "relw": round(max(0.18, widget.winfo_width() / parent_w), 4),
            "relh": round(max(0.18, widget.winfo_height() / parent_h), 4),
        }
        self._panel_layout_dirty = False
        self._set_command_status(f"{panel.title()} panel position saved")

    def _start_panel_resize(self, panel: str, event: Any) -> None:
        widget = self._panel_widget(panel)
        parent = self.workspace_frame
        if widget is None or parent is None:
            return
        self._resize_panel_state[panel] = {
            "start_x": float(event.x_root),
            "start_y": float(event.y_root),
            "start_w": float(widget.winfo_width()),
            "start_h": float(widget.winfo_height()),
            "relx": float(widget.winfo_x() / max(parent.winfo_width(), 1)),
            "rely": float(widget.winfo_y() / max(parent.winfo_height(), 1)),
        }
        widget.lift()
        self._set_command_status(f"Scaling {panel.title()} panel")

    def _minimum_panel_size(self, panel: str) -> tuple[int, int]:
        if panel == "core":
            return (320, 230)
        if panel == "side":
            return (260, 300)
        if panel == "code":
            return (560, 360)
        if panel == "news":
            return (420, 330)
        if panel == "article":
            return (480, 360)
        if panel == "video_news":
            return (420, 330)
        if panel == "video":
            return (500, 420)
        if panel == "browser":
            return (700, 480)
        return (320, 200)

    def _maximum_panel_size_ratio(self, panel: str) -> tuple[float, float]:
        if panel == "core":
            return (0.46, 0.48)
        if panel == "chat":
            return (0.50, 0.42)
        if panel == "side":
            return (0.30, 0.82)
        if panel == "code":
            return (0.62, 0.68)
        if panel == "news":
            return (0.46, 0.62)
        if panel == "article":
            return (0.62, 0.78)
        if panel == "video_news":
            return (0.46, 0.66)
        if panel == "video":
            return (0.60, 0.76)
        if panel == "browser":
            return (0.99, 0.99)
        return (0.50, 0.50)

    def _resize_command_panel(self, panel: str, event: Any) -> None:
        widget = self._panel_widget(panel)
        parent = self.workspace_frame
        state = self._resize_panel_state.get(panel)
        if widget is None or parent is None or not state:
            return
        parent_w = max(parent.winfo_width(), 1)
        parent_h = max(parent.winfo_height(), 1)
        min_w, min_h = self._minimum_panel_size(panel)
        max_w_ratio, max_h_ratio = self._maximum_panel_size_ratio(panel)
        max_w = max(min_w, int(parent_w * max_w_ratio))
        max_h = max(min_h, int(parent_h * max_h_ratio))
        x = max(0, widget.winfo_x())
        y = max(0, widget.winfo_y())
        new_w = state["start_w"] + (event.x_root - state["start_x"])
        new_h = state["start_h"] + (event.y_root - state["start_y"])
        new_w = max(min_w, min(max_w, parent_w - x, new_w))
        new_h = max(min_h, min(max_h, parent_h - y, new_h))
        widget.place(
            relx=x / parent_w,
            rely=y / parent_h,
            relwidth=max(0.18, new_w / parent_w),
            relheight=max(0.18, new_h / parent_h),
        )
        self._schedule_layout_autosave(panel_change=True)

    def _finish_panel_resize(self, panel: str, event: Any) -> None:
        self._resize_command_panel(panel, event)
        self._finish_panel_drag(panel, event)
        self._resize_panel_state.pop(panel, None)
        self._set_command_status(f"{panel.title()} panel size saved")

    def _reset_draggable_panel_layout(self) -> None:
        self._session_panel_layout = json.loads(json.dumps(DEFAULT_DRAGGABLE_PANEL_LAYOUT))
        for panel in ["core", "chat", "side", "code", "news", "article", "video_news", "video", "browser"]:
            self._session_panel_visibility[panel] = False
        self._apply_command_center_visibility()
        self._set_command_status("Command Center layout reset")
        self._append_chat("System", "Command Center panels reset inside the main window.")

    def _apply_command_center_visibility(self) -> None:
        for panel in ["core", "chat", "side", "code", "news", "article", "video_news", "video", "browser"]:
            widget = self._panel_widget(panel)
            if widget is None:
                continue
            if self._session_panel_visibility.get(panel, False):
                self._place_command_panel(panel)
            else:
                widget.place_forget()

    def _toggle_command_center_panel(self, panel: str) -> None:
        current = bool(self._session_panel_visibility.get(panel, False))
        self._set_command_center_panel_visible(panel, not current)

    def _set_command_center_panel_visible(self, panel: str, visible: bool) -> None:
        self._session_panel_visibility[panel] = visible

        widget: Any | None = None
        if panel == "core":
            widget = self.core_panel
        elif panel == "chat":
            widget = self.chat_panel
        elif panel == "side":
            widget = self.side_panel_container
        elif panel == "code":
            widget = self.code_panel
        elif panel == "news":
            widget = self.news_panel
        elif panel == "article":
            widget = self.article_panel
        elif panel == "video_news":
            widget = self.video_news_panel
        elif panel == "video":
            widget = self.video_panel
        elif panel == "browser":
            widget = self.browser_panel

        if widget is None:
            return
        if visible:
            self._place_command_panel(panel)
            if panel == "code":
                self.after(80, self._refresh_coding_workspace_files)
            if panel == "news":
                self.after(80, self.refresh_news_panel)
            if panel == "video_news":
                self.after(80, self.refresh_video_news_panel)
            if panel == "browser":
                self.after(120, self._ensure_browser_running)
            self._set_command_status(f"{panel.title()} panel restored")
        else:
            widget.place_forget()
            self._set_command_status(f"{panel.title()} panel collapsed")

    def open_panel_manager_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Panel Manager")
        self._apply_window_icon(window)
        window.geometry("520x420+120+120")
        window.minsize(460, 360)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            window,
            text="Panel Manager",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="Toggle Command Center sections or reset the in-window draggable layout.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=460,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        controls = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        for column in range(3):
            controls.grid_columnconfigure(column, weight=1)
        for index, panel in enumerate(["core", "chat", "side", "code", "news", "article", "video", "browser"]):
            ctk.CTkButton(
                controls,
                text=f"Toggle {panel.replace('_', ' ').title()}",
                command=lambda name=panel: self._toggle_command_center_panel(name),
            ).grid(row=index // 3, column=index % 3, sticky="ew", padx=8, pady=6)

        layout_tools = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        layout_tools.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        layout_tools.grid_columnconfigure(0, weight=1)
        layout_tools.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            layout_tools,
            text="Reset Panel Positions",
            command=self._reset_draggable_panel_layout,
        ).grid(row=0, column=0, sticky="ew", padx=8, pady=10)
        ctk.CTkButton(
            layout_tools,
            text="Restore All Panels",
            command=lambda: [self._set_command_center_panel_visible(panel, True) for panel in ["core", "chat", "side", "code", "news", "article", "video", "browser"]],
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=10)

    def _floating_panel_specs(self) -> list[tuple[str, ctk.StringVar, str]]:
        return [
            ("Active Window", self.window_var, "active_window"),
            ("Vitals", self.monitor_summary_var, "vitals"),
            ("Music", self.music_var, "music"),
            ("Command", self.command_var, "command"),
            ("Risk", self.risk_var, "risk"),
            ("Last Action", self.last_action_var, "last_action"),
        ]

    def _floating_panel_lookup(self) -> dict[str, tuple[str, ctk.StringVar, str]]:
        return {key: (title, variable, key) for title, variable, key in self._floating_panel_specs()}

    def _open_floating_status_panel(self, title: str, variable: ctk.StringVar, key: str) -> None:
        existing = self.floating_panels.get(key)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            return

        window = ctk.CTkToplevel(self)
        self.floating_panels[key] = window
        window.title(f"JARVIS - {title}")
        self._apply_window_icon(window)
        window.geometry("340x150+180+180")
        window.minsize(280, 120)
        window.configure(fg_color="#050812")
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)
        window.protocol("WM_DELETE_WINDOW", lambda item_key=key: self._close_floating_status_panel(item_key))

        header = ctk.CTkFrame(window, fg_color="#07111f", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=title.upper(), text_color="#8be9ff", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=8)
        ctk.CTkButton(header, text="X", width=36, command=lambda item_key=key: self._close_floating_status_panel(item_key)).grid(row=0, column=1, padx=8, pady=7)

        body = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8, border_width=1, border_color="#123f5a")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(body, textvariable=variable, text_color="#eefbff", justify="left", wraplength=290).grid(row=0, column=0, sticky="ew", padx=12, pady=14)

    def _close_floating_status_panel(self, key: str) -> None:
        window = self.floating_panels.pop(key, None)
        if window is not None and window.winfo_exists():
            window.destroy()

    def open_gesture_pad_window(self) -> None:
        if self.gesture_window is not None and self.gesture_window.winfo_exists():
            self.gesture_window.deiconify()
            self.gesture_window.lift()
            return
        window = ctk.CTkToplevel(self)
        self.gesture_window = window
        window.title("Webcam Gesture Control")
        self._apply_window_icon(window)
        window.geometry("720x650+160+90")
        window.minsize(600, 540)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.protocol("WM_DELETE_WINDOW", self._close_gesture_window)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            window,
            text="Webcam Gesture Control",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#8be9ff",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="Hold an index-point to guide the cursor. Pinch thumb and index to click in Armed mode. A greeting wave requires a clear open palm moving side to side.",
            text_color="#d9f7ff",
            anchor="w",
            wraplength=670,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        preview_frame = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8, border_width=1, border_color="#123f5a")
        preview_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 12))
        preview_frame.grid_columnconfigure(0, weight=1)
        preview_frame.grid_rowconfigure(0, weight=1)
        self.gesture_preview_label = ctk.CTkLabel(
            preview_frame,
            text="Camera preview appears here after gesture control starts.",
            text_color="#6edcff",
        )
        self.gesture_preview_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        footer = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)
        status_stack = ctk.CTkFrame(footer, fg_color="transparent")
        status_stack.grid(row=0, column=0, rowspan=2, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(status_stack, textvariable=self.gesture_status_var, text_color="#eefbff", anchor="w", wraplength=390).pack(fill="x")
        ctk.CTkLabel(status_stack, textvariable=self.gesture_backend_var, text_color="#6edcff", anchor="w").pack(fill="x")
        controls = ctk.CTkFrame(footer, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=10, pady=(8, 3))
        ctk.CTkLabel(controls, text="Mode", text_color="#8be9ff").pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            controls,
            values=["Safe", "Armed", "Disabled"],
            variable=self.gesture_mode_var,
            width=100,
            command=self._set_webcam_gesture_mode,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="Start", width=72, command=self.start_webcam_gestures).pack(side="left", padx=4)
        ctk.CTkButton(controls, text="Stop", width=72, fg_color="#7b2633", hover_color="#a13343", command=self.stop_webcam_gestures).pack(side="left", padx=4)
        ctk.CTkLabel(
            footer,
            text="Safe: point + wave    Armed: point + pinch click    Motion blobs never control the cursor",
            text_color="#9db7c7",
            anchor="e",
        ).grid(row=1, column=1, sticky="e", padx=14, pady=(0, 8))

    def _close_gesture_window(self) -> None:
        if self.gesture_window is not None and self.gesture_window.winfo_exists():
            self.gesture_window.destroy()
        self.gesture_window = None
        self.gesture_preview_label = None

    def _set_webcam_gesture_mode(self, mode: str) -> None:
        normalized = mode if mode in {"Safe", "Armed", "Disabled"} else "Safe"
        self.assistant.settings["webcam_gesture_mode"] = normalized
        save_settings(self.assistant.settings)
        self.gesture_mode_var.set(normalized)
        self.gesture_status_var.set(f"Gesture mode set to {normalized}.")
        self._set_command_status(f"Webcam gestures: {normalized}")

    def start_webcam_gestures(self) -> None:
        if cv2 is None or np is None:
            message = "Webcam gestures need OpenCV and NumPy. Install requirements, then try again."
            self.gesture_status_var.set(message)
            self._append_chat("System", message)
            return
        if self._gesture_thread is not None and self._gesture_thread.is_alive():
            self.gesture_status_var.set("Webcam gestures are already running.")
            return
        self._gesture_stop.clear()
        self._gesture_wave_positions.clear()
        self._gesture_open_palm_frames = 0
        self._gesture_point_frames = 0
        self._gesture_pinch_frames = 0
        self._gesture_pinch_release_frames = 0
        self._gesture_cursor_samples.clear()
        self._gesture_thread = threading.Thread(target=self._webcam_gesture_worker, daemon=True)
        self._gesture_thread.start()
        self.assistant.settings["webcam_gestures_enabled"] = True
        save_settings(self.assistant.settings)
        self.gesture_enabled_var.set("Starting")
        self.gesture_status_var.set("Opening webcam...")
        self._set_command_status("Starting webcam gesture control...")

    def stop_webcam_gestures(self) -> None:
        self._gesture_stop.set()
        capture = self._gesture_capture
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        self._gesture_capture = None
        self.assistant.settings["webcam_gestures_enabled"] = False
        save_settings(self.assistant.settings)
        self.gesture_enabled_var.set("Off")
        self.gesture_status_var.set("Webcam gestures are off.")
        self._set_command_status("Webcam gesture control stopped")

    def _webcam_gesture_worker(self) -> None:
        camera_index = int(self.assistant.settings.get("webcam_camera_index", 0))
        capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW if platform.system().lower() == "windows" else 0)
        self._gesture_capture = capture
        if not capture.isOpened():
            capture.release()
            self._gesture_capture = None
            self.after(0, lambda: self._webcam_gesture_failed(f"Could not open webcam {camera_index}."))
            return
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        capture.set(cv2.CAP_PROP_FPS, 24)
        legacy_hands = None
        task_hand_landmarker = None
        background = None
        if mp is not None and hasattr(mp, "tasks") and HAND_LANDMARKER_MODEL_PATH.exists():
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_LANDMARKER_MODEL_PATH)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.65,
                min_hand_presence_confidence=0.65,
                min_tracking_confidence=0.65,
            )
            task_hand_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
            backend = "MediaPipe Tasks hand landmarks"
        elif mp is not None and hasattr(mp, "solutions"):
            legacy_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=1,
                min_detection_confidence=0.65,
                min_tracking_confidence=0.65,
            )
            backend = "MediaPipe legacy hand landmarks"
        else:
            background = cv2.createBackgroundSubtractorMOG2(history=160, varThreshold=24, detectShadows=False)
            backend = "OpenCV diagnostic fallback (gestures disabled)"
        self.after(0, lambda name=backend: self._webcam_gesture_started(name))
        last_preview = 0.0
        try:
            while not self._gesture_stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    time.sleep(0.08)
                    continue
                if self.assistant.settings.get("webcam_mirror_preview", True):
                    frame = cv2.flip(frame, 1)
                gesture_label = "Watching"
                if task_hand_landmarker is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    media_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    result = task_hand_landmarker.detect_for_video(media_image, int(time.monotonic() * 1000))
                    if result.hand_landmarks:
                        points = result.hand_landmarks[0]
                        self._draw_task_hand_landmarks(frame, points)
                        gesture_label = self._process_mediapipe_hand(points, frame.shape[1], frame.shape[0])
                    else:
                        self._reset_hand_pose_tracking()
                elif legacy_hands is not None:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = legacy_hands.process(rgb)
                    if results.multi_hand_landmarks:
                        landmarks = results.multi_hand_landmarks[0]
                        mp.solutions.drawing_utils.draw_landmarks(frame, landmarks, mp.solutions.hands.HAND_CONNECTIONS)
                        gesture_label = self._process_mediapipe_hand(landmarks.landmark, frame.shape[1], frame.shape[0])
                    else:
                        self._reset_hand_pose_tracking()
                else:
                    gesture_label = self._process_opencv_wave(frame, background)
                cv2.putText(frame, gesture_label, (16, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 220, 80), 2, cv2.LINE_AA)
                now = time.monotonic()
                if now - last_preview >= 0.10:
                    preview = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    preview = cv2.resize(preview, (600, 450), interpolation=cv2.INTER_AREA)
                    image = Image.fromarray(preview)
                    self.after(0, lambda item=image: self._update_webcam_preview(item))
                    last_preview = now
        except Exception as exc:
            self.after(0, lambda error=str(exc): self._webcam_gesture_failed(error))
        finally:
            if task_hand_landmarker is not None:
                task_hand_landmarker.close()
            if legacy_hands is not None:
                legacy_hands.close()
            capture.release()
            self._gesture_capture = None
            self.after(0, self._webcam_gesture_stopped)

    @staticmethod
    def _hand_distance(points: Any, first: int, second: int) -> float:
        return math.sqrt(
            (float(points[first].x) - float(points[second].x)) ** 2
            + (float(points[first].y) - float(points[second].y)) ** 2
            + (float(getattr(points[first], "z", 0.0)) - float(getattr(points[second], "z", 0.0))) ** 2
        )

    @classmethod
    def _hand_joint_angle(cls, points: Any, first: int, joint: int, last: int) -> float:
        a = (
            float(points[first].x) - float(points[joint].x),
            float(points[first].y) - float(points[joint].y),
            float(getattr(points[first], "z", 0.0)) - float(getattr(points[joint], "z", 0.0)),
        )
        b = (
            float(points[last].x) - float(points[joint].x),
            float(points[last].y) - float(points[joint].y),
            float(getattr(points[last], "z", 0.0)) - float(getattr(points[joint], "z", 0.0)),
        )
        denominator = math.sqrt(sum(value * value for value in a)) * math.sqrt(sum(value * value for value in b))
        if denominator <= 1e-8:
            return 0.0
        cosine = max(-1.0, min(1.0, sum(a[index] * b[index] for index in range(3)) / denominator))
        return math.degrees(math.acos(cosine))

    @classmethod
    def _finger_is_extended(cls, points: Any, mcp: int, pip: int, dip: int, tip: int) -> bool:
        pip_angle = cls._hand_joint_angle(points, mcp, pip, dip)
        dip_angle = cls._hand_joint_angle(points, pip, dip, tip)
        return (
            pip_angle >= 150.0
            and dip_angle >= 145.0
            and cls._hand_distance(points, 0, tip) > cls._hand_distance(points, 0, pip) * 1.12
        )

    def _reset_hand_pose_tracking(self) -> None:
        self._gesture_wave_positions.clear()
        self._gesture_open_palm_frames = 0
        self._gesture_point_frames = 0
        self._gesture_pinch_frames = 0
        self._gesture_pinch_release_frames = 0
        self._gesture_pinched = False
        self._gesture_cursor_samples.clear()

    def _draw_task_hand_landmarks(self, frame: Any, points: Any) -> None:
        connections = (
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
        )
        width = frame.shape[1]
        height = frame.shape[0]
        pixels = [(int(point.x * width), int(point.y * height)) for point in points]
        for first, second in connections:
            cv2.line(frame, pixels[first], pixels[second], (60, 200, 255), 2, cv2.LINE_AA)
        for index, pixel in enumerate(pixels):
            color = (80, 255, 160) if index in {4, 8, 12, 16, 20} else (255, 220, 80)
            cv2.circle(frame, pixel, 4, color, -1, cv2.LINE_AA)

    def _move_cursor_from_point(self, point_x: float, point_y: float) -> None:
        samples = self._gesture_cursor_samples
        samples.append((point_x, point_y))
        del samples[:-5]
        stable_x = float(np.median([sample[0] for sample in samples]))
        stable_y = float(np.median([sample[1] for sample in samples]))
        screen_width, screen_height = screen_size()
        margin_x = 0.14
        margin_y = 0.12
        target_x = int((max(margin_x, min(1.0 - margin_x, stable_x)) - margin_x) / (1.0 - margin_x * 2) * screen_width)
        target_y = int((max(margin_y, min(1.0 - margin_y, stable_y)) - margin_y) / (1.0 - margin_y * 2) * screen_height)
        if self._gesture_last_cursor is None:
            smooth_x, smooth_y = target_x, target_y
        else:
            old_x, old_y = self._gesture_last_cursor
            distance = math.hypot(target_x - old_x, target_y - old_y)
            if distance < 5:
                return
            blend = 0.22 if distance < 100 else 0.34
            smooth_x = int(old_x * (1.0 - blend) + target_x * blend)
            smooth_y = int(old_y * (1.0 - blend) + target_y * blend)
        self._gesture_last_cursor = clamp_screen_point(smooth_x, smooth_y)
        ctypes.windll.user32.SetCursorPos(*self._gesture_last_cursor)

    def _process_mediapipe_hand(self, points: Any, frame_width: int, frame_height: int) -> str:
        del frame_width, frame_height
        palm_scale = max(0.001, self._hand_distance(points, 0, 9))
        extended = [
            self._finger_is_extended(points, 5, 6, 7, 8),
            self._finger_is_extended(points, 9, 10, 11, 12),
            self._finger_is_extended(points, 13, 14, 15, 16),
            self._finger_is_extended(points, 17, 18, 19, 20),
        ]
        thumb_open = self._hand_distance(points, 4, 5) / palm_scale > 0.52
        open_palm = all(extended) and thumb_open
        pointing = extended[0] and not any(extended[1:])
        control_pose = not any(extended[1:])
        mode = str(self.assistant.settings.get("webcam_gesture_mode", "Safe"))

        if open_palm:
            self._gesture_open_palm_frames += 1
            self._gesture_point_frames = 0
            self._gesture_cursor_samples.clear()
            if self._gesture_open_palm_frames >= 5:
                self._track_webcam_wave(float(points[9].x))
            return "Open palm - wave side to side"
        self._gesture_open_palm_frames = 0
        self._gesture_wave_positions.clear()

        pinch_ratio = self._hand_distance(points, 4, 8) / palm_scale
        pinch_candidate = control_pose and pinch_ratio <= 0.30
        pinch_released = pinch_ratio >= 0.43
        if pinch_candidate:
            self._gesture_pinch_frames += 1
            self._gesture_pinch_release_frames = 0
        elif pinch_released:
            self._gesture_pinch_release_frames += 1
            self._gesture_pinch_frames = 0
            if self._gesture_pinch_release_frames >= 3:
                self._gesture_pinched = False
        else:
            self._gesture_pinch_frames = max(0, self._gesture_pinch_frames - 1)

        if self._gesture_pinch_frames >= 3 and not self._gesture_pinched:
            self._gesture_pinched = True
            if mode == "Armed" and time.monotonic() - self._gesture_last_click_at > 0.8:
                click_mouse()
                self._gesture_last_click_at = time.monotonic()
                self.after(0, lambda: self._set_command_status("Gesture: deliberate pinch click"))

        if pointing and not self._gesture_pinched and mode != "Disabled":
            self._gesture_point_frames += 1
            if self._gesture_point_frames >= 3:
                self._move_cursor_from_point(float(points[8].x), float(points[8].y))
        else:
            self._gesture_point_frames = 0
            if not pinch_candidate:
                self._gesture_cursor_samples.clear()

        if self._gesture_pinched or pinch_candidate:
            return "Pinch click" if mode == "Armed" else "Pinch held - click disabled in Safe mode"
        if pointing:
            return "Pointing - cursor active" if self._gesture_point_frames >= 3 else "Hold point steady"
        return "Hand detected - make a clear point"

    def _process_opencv_wave(self, frame: Any, background: Any) -> str:
        if background is None:
            return "Fallback tracker unavailable"
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        skin = cv2.inRange(ycrcb, np.array([0, 130, 70], dtype=np.uint8), np.array([255, 185, 140], dtype=np.uint8))
        motion = background.apply(frame)
        mask = cv2.bitwise_and(skin, motion)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return "Watching for a wave"
        contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(contour)
        frame_area = frame.shape[0] * frame.shape[1]
        if area < frame_area * 0.012:
            return "Watching for a wave"
        x, y, width, height = cv2.boundingRect(contour)
        cv2.rectangle(frame, (x, y), (x + width, y + height), (60, 230, 255), 2)
        return "Motion detected - landmark gestures unavailable"

    def _track_webcam_wave(self, center_x: float) -> None:
        now = time.monotonic()
        positions = self._gesture_wave_positions
        if positions and now - positions[-1][1] > 0.42:
            positions.clear()
        if not positions or abs(center_x - positions[-1][0]) >= 0.022:
            positions.append((center_x, now))
        positions[:] = [(x, stamp) for x, stamp in positions if now - stamp <= 2.2]
        if len(positions) < 8:
            return
        directions: list[int] = []
        total_travel = 0.0
        for index in range(1, len(positions)):
            delta = positions[index][0] - positions[index - 1][0]
            total_travel += abs(delta)
            if abs(delta) >= 0.018:
                direction = 1 if delta > 0 else -1
                if not directions or directions[-1] != direction:
                    directions.append(direction)
        duration = positions[-1][1] - positions[0][1]
        span = max(position[0] for position in positions) - min(position[0] for position in positions)
        cooldown = int(self.assistant.settings.get("webcam_wave_cooldown_seconds", 8))
        strict_wave = len(directions) >= 4 and span >= 0.16 and total_travel >= 0.38 and 0.65 <= duration <= 2.2
        if strict_wave and now - self._gesture_last_wave_at >= max(4, cooldown):
            self._gesture_last_wave_at = now
            positions.clear()
            self.after(0, self._respond_to_webcam_wave)

    def _respond_to_webcam_wave(self) -> None:
        user_name = str(self.assistant.personality.get("user_name") or "there")
        message = f"Hello, {user_name}. Nice to see you."
        self.gesture_status_var.set("Wave recognized. Greeting delivered.")
        self._append_chat("JARVIS", message)
        self._set_overlay_response(f"JARVIS: {message}")
        self._set_command_status("Gesture: wave recognized")
        self.assistant.record_action("webcam_wave", {}, "safe", True, message, verified=True)
        if self.voice_enabled_var.get() and self.assistant.settings.get("webcam_wave_speaks", True):
            self.speak(message)

    def _update_webcam_preview(self, image: Image.Image) -> None:
        label = self.gesture_preview_label
        if label is None or not label.winfo_exists():
            return
        self._gesture_preview_image = ImageTk.PhotoImage(image=image)
        label.configure(image=self._gesture_preview_image, text="")

    def _webcam_gesture_started(self, backend: str) -> None:
        self.gesture_enabled_var.set("On")
        self.gesture_backend_var.set(f"Backend: {backend}")
        self.gesture_status_var.set("Webcam gestures active. Wave hello.")
        self._append_chat("System", f"Webcam gesture control active using {backend}.")
        self._set_command_status("Webcam gestures active")

    def _webcam_gesture_failed(self, error: str) -> None:
        self._gesture_stop.set()
        self.assistant.settings["webcam_gestures_enabled"] = False
        save_settings(self.assistant.settings)
        self.gesture_enabled_var.set("Error")
        self.gesture_status_var.set(f"Camera error: {error}")
        self._append_chat("System", f"Webcam gesture control failed: {error}")
        self._set_command_status("Webcam gesture control unavailable")

    def _webcam_gesture_stopped(self) -> None:
        self.gesture_enabled_var.set("Off")
        if not self._gesture_stop.is_set():
            self.gesture_status_var.set("Webcam gesture tracking ended.")

    def _draw_gesture_pad_background(self) -> None:
        canvas = self.gesture_canvas
        if canvas is None:
            return
        canvas.delete("all")
        width = max(420, int(canvas.winfo_width() or 560))
        height = max(300, int(canvas.winfo_height() or 360))
        canvas.create_rectangle(0, 0, width, height, fill="#06101d", outline="")
        for x in range(40, width, 80):
            canvas.create_line(x, 0, x, height, fill="#0b2740")
        for y in range(40, height, 80):
            canvas.create_line(0, y, width, y, fill="#0b2740")
        canvas.create_oval(width // 2 - 46, height // 2 - 46, width // 2 + 46, height // 2 + 46, outline="#1fdcff", width=2)
        canvas.create_oval(width // 2 - 10, height // 2 - 10, width // 2 + 10, height // 2 + 10, fill="#21d4ff", outline="#c8f7ff")
        hints = [
            ("RIGHT", "Overlay"),
            ("LEFT", "Hide overlay"),
            ("UP", "Voice"),
            ("DOWN", "Toggle side"),
            ("TAP", "Missions"),
        ]
        for index, (gesture, action) in enumerate(hints):
            canvas.create_text(22, 24 + index * 24, text=f"{gesture:<6} {action}", anchor="w", fill="#8be9ff", font=("Consolas", 11, "bold"))
        self.gesture_points = []

    def _gesture_start(self, event: Any) -> None:
        self.gesture_points = [(int(event.x), int(event.y))]
        self._draw_gesture_pad_background()

    def _gesture_drag(self, event: Any) -> None:
        if self.gesture_canvas is None:
            return
        x = int(event.x)
        y = int(event.y)
        if self.gesture_points:
            last_x, last_y = self.gesture_points[-1]
            self.gesture_canvas.create_line(last_x, last_y, x, y, fill="#27d8ff", width=4, capstyle="round")
        self.gesture_points.append((x, y))

    def _gesture_release(self, event: Any) -> None:
        self.gesture_points.append((int(event.x), int(event.y)))
        gesture = self._classify_gesture(self.gesture_points)
        action = self._gesture_action_for(gesture)
        if not action:
            self.gesture_status_var.set("Gesture unclear. Even futuristic systems enjoy legible handwriting.")
            self._set_command_status("Gesture ignored")
            return
        self._execute_gesture_action(gesture, action)

    def _classify_gesture(self, points: list[tuple[int, int]]) -> str:
        if len(points) < 2:
            return "tap"
        start_x, start_y = points[0]
        end_x, end_y = points[-1]
        dx = end_x - start_x
        dy = end_y - start_y
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < 38:
            return "tap"
        if abs(dx) >= abs(dy):
            return "swipe_right" if dx > 0 else "swipe_left"
        return "swipe_down" if dy > 0 else "swipe_up"

    def _gesture_action_for(self, gesture: str) -> str:
        actions = self.assistant.settings.get("gesture_actions", DEFAULT_GESTURE_ACTIONS)
        if not isinstance(actions, dict):
            actions = DEFAULT_GESTURE_ACTIONS
        return str(actions.get(gesture, "")).strip().lower()

    def _execute_gesture_action(self, gesture: str, action: str) -> None:
        label = gesture.replace("_", " ").title()
        if action == "show overlay":
            self.show_overlay()
            message = "Overlay summoned."
        elif action == "hide overlay":
            self.hide_overlay()
            message = "Overlay dismissed."
        elif action == "voice capture":
            self.listen_once()
            message = "Voice capture started."
        elif action == "toggle side panel":
            self._toggle_command_center_panel("side")
            message = "Side telemetry toggled."
        elif action == "mission dashboard":
            self.open_mission_dashboard_window()
            message = "Mission dashboard opened."
        else:
            message = f"Gesture mapped to unsupported action: {action}"
        self.gesture_status_var.set(f"{label}: {message}")
        self._append_chat("System", f"Gesture {label}: {message}")
        self._set_command_status(f"Gesture: {message}")
        self.assistant.record_action(f"gesture:{gesture}", {"action": action}, "safe", True, message, verified=True)

    def open_workspace_layout_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Workspace Layouts")
        self._apply_window_icon(window)
        window.geometry("720x560+180+120")
        window.minsize(600, 460)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            window,
            text="Workspace Layouts",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#8be9ff",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="Swap the Command Center between full dashboard, focus, diagnostics, and minimal console views.",
            text_color="#d9f7ff",
            anchor="w",
            wraplength=640,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        list_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 12))
        list_frame.grid_columnconfigure(0, weight=1)
        self._refresh_workspace_layouts(list_frame)

        footer = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer,
            text=f"Current layout: {self.assistant.settings.get('last_workspace_layout', 'Full Command Center')}",
            text_color="#eefbff",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        ctk.CTkButton(footer, text="Save Current", width=120, command=lambda: self._save_current_workspace_layout(list_frame)).grid(row=0, column=1, padx=(0, 12), pady=10)

    def _workspace_layouts(self) -> list[dict[str, Any]]:
        layouts = self.assistant.settings.get("workspace_layouts", DEFAULT_WORKSPACE_LAYOUTS)
        if not isinstance(layouts, list):
            layouts = DEFAULT_WORKSPACE_LAYOUTS.copy()
            self.assistant.settings["workspace_layouts"] = layouts
            save_settings(self.assistant.settings)
        return layouts

    def _refresh_workspace_layouts(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()
        for index, layout in enumerate(self._workspace_layouts()):
            name = str(layout.get("name", "Workspace"))
            description = str(layout.get("description", ""))
            row = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6, border_width=1, border_color="#123f5a")
            row.grid(row=index, column=0, sticky="ew", padx=10, pady=(10 if index == 0 else 4, 8))
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=15, weight="bold"), text_color="#8be9ff", anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
            ctk.CTkLabel(row, text=description, text_color="#d9f7ff", anchor="w", wraplength=500, justify="left").grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 10))
            ctk.CTkButton(row, text="Apply", width=92, command=lambda item=layout: self._apply_workspace_layout(item)).grid(row=0, column=1, rowspan=2, padx=12, pady=10)

    def _apply_workspace_layout(self, layout: dict[str, Any]) -> None:
        name = str(layout.get("name", "Workspace"))
        for panel in ["core", "chat", "side", "code", "news", "article", "video_news", "video", "browser"]:
            if panel in layout:
                self._set_command_center_panel_visible(panel, bool(layout.get(panel)))
        geometry = str(layout.get("geometry", "")).strip()
        if re.match(r"^\d{3,4}x\d{3,4}$", geometry):
            self.geometry(geometry)
        panel_layout = layout.get("panel_layout")
        if isinstance(panel_layout, dict):
            self._session_panel_layout = json.loads(json.dumps(panel_layout))
            self.after(80, self._place_command_panels)
        for key in list(self.floating_panels.keys()):
            self._close_floating_status_panel(key)
        if layout.get("overlay"):
            self.show_overlay()
        else:
            self.hide_overlay()
        self.assistant.settings["last_workspace_layout"] = name
        save_settings(self.assistant.settings)
        self._append_chat("System", f"Workspace layout applied: {name}.")
        self._set_command_status(f"Layout: {name}")
        self.assistant.record_action(f"layout:{name}", {}, "safe", True, f"Applied workspace layout {name}", verified=True)

    def _save_current_workspace_layout(self, list_frame: ctk.CTkScrollableFrame) -> None:
        name = f"Custom Layout {dt.datetime.now().strftime('%H%M')}"
        current_geometry = self.geometry().split("+")[0]
        layout = {
            "name": name,
            "description": "Saved from the current Command Center panel state.",
            "core": bool(self._session_panel_visibility.get("core", False)),
            "chat": bool(self._session_panel_visibility.get("chat", False)),
            "side": bool(self._session_panel_visibility.get("side", False)),
            "code": bool(self._session_panel_visibility.get("code", False)),
            "news": bool(self._session_panel_visibility.get("news", False)),
            "article": bool(self._session_panel_visibility.get("article", False)),
            "video_news": bool(self._session_panel_visibility.get("video_news", False)),
            "video": bool(self._session_panel_visibility.get("video", False)),
            "browser": bool(self._session_panel_visibility.get("browser", False)),
            "geometry": current_geometry,
            "overlay": self.overlay_window is not None and self.overlay_window.winfo_exists() and self.overlay_window.state() != "withdrawn",
            "panel_layout": json.loads(json.dumps(self._session_panel_layout)),
            "float_panels": [],
        }
        layouts = [item for item in self._workspace_layouts() if str(item.get("name", "")).lower() != name.lower()]
        layouts.append(layout)
        self.assistant.settings["workspace_layouts"] = layouts
        self.assistant.settings["last_workspace_layout"] = name
        save_settings(self.assistant.settings)
        self._refresh_workspace_layouts(list_frame)
        self._append_chat("System", f"Saved workspace layout: {name}.")
        self._set_command_status(f"Saved layout: {name}")

    def open_mission_dashboard_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Mission Dashboard")
        self._apply_window_icon(window)
        window.geometry("760x680+140+100")
        window.minsize(640, 540)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            window,
            text="Mission Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#8be9ff",
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(
            window,
            text="Run saved multi-step workflows through JARVIS' approved command router. Risky steps still stop for confirmation.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=700,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 12))

        form = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        form.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(form, text="Name", text_color="#d9f7ff").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        name_entry = ctk.CTkEntry(form, placeholder_text="Example: Recording Setup")
        name_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 6))
        ctk.CTkLabel(form, text="Steps", text_color="#d9f7ff").grid(row=1, column=0, sticky="nw", padx=12, pady=6)
        steps_entry = ctk.CTkEntry(form, placeholder_text="Semicolon-separated commands, example: focus mode; open chrome; start timer for 25 minutes")
        steps_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        ctk.CTkButton(
            form,
            text="Save Mission",
            width=120,
            command=lambda: self._add_mission_template(name_entry, steps_entry, mission_list),
        ).grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=12)

        mission_list = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        mission_list.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        mission_list.grid_columnconfigure(0, weight=1)
        self._refresh_mission_list(mission_list)

    def _mission_templates(self) -> list[dict[str, Any]]:
        templates = self.assistant.settings.get("mission_templates", DEFAULT_MISSION_TEMPLATES)
        if not isinstance(templates, list) or not templates:
            templates = DEFAULT_MISSION_TEMPLATES
            self.assistant.settings["mission_templates"] = templates
            save_settings(self.assistant.settings)
        clean_templates: list[dict[str, Any]] = []
        for template in templates:
            if not isinstance(template, dict):
                continue
            name = str(template.get("name", "")).strip()
            steps = template.get("steps", [])
            if not name or not isinstance(steps, list):
                continue
            clean_steps = [str(step).strip() for step in steps if str(step).strip()]
            if clean_steps:
                clean_templates.append(
                    {
                        "name": name[:80],
                        "description": str(template.get("description", "")).strip()[:220],
                        "steps": clean_steps[:12],
                    }
                )
        return clean_templates

    def _refresh_mission_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        templates = self._mission_templates()
        if not templates:
            ctk.CTkLabel(list_frame, text="No missions saved yet.", text_color="#d9f7ff", anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        for row, template in enumerate(templates):
            card = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6, border_width=1, border_color="#123f5a")
            card.grid(row=row, column=0, sticky="ew", padx=8, pady=7)
            card.grid_columnconfigure(0, weight=1)
            title = str(template.get("name", "Mission"))
            description = str(template.get("description", "")).strip()
            steps = [str(step) for step in template.get("steps", [])]
            body = title
            if description:
                body += f"\n{description}"
            body += "\n" + "\n".join(f"{index + 1}. {step}" for index, step in enumerate(steps))
            ctk.CTkLabel(card, text=body, anchor="w", justify="left", wraplength=520, text_color="#eefbff").grid(row=0, column=0, sticky="ew", padx=12, pady=10)
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.grid(row=0, column=1, sticky="e", padx=10, pady=10)
            ctk.CTkButton(actions, text="Run", width=78, command=lambda item=template: self._start_mission(item)).grid(row=0, column=0, pady=(0, 6))
            ctk.CTkButton(actions, text="Remove", width=78, command=lambda name=title: self._remove_mission_template(name, list_frame)).grid(row=1, column=0)

    def _add_mission_template(self, name_entry: ctk.CTkEntry, steps_entry: ctk.CTkEntry, list_frame: ctk.CTkScrollableFrame) -> None:
        name = name_entry.get().strip()
        raw_steps = steps_entry.get().strip()
        steps = [step.strip() for step in raw_steps.split(";") if step.strip()]
        if not name:
            messagebox.showerror("JARVIS", "Give the mission a name first.")
            return
        if not steps:
            messagebox.showerror("JARVIS", "Add at least one semicolon-separated command.")
            return
        templates = [template for template in self._mission_templates() if str(template.get("name", "")).lower() != name.lower()]
        templates.append({"name": name[:80], "description": "Custom mission.", "steps": steps[:12]})
        self.assistant.settings["mission_templates"] = templates
        save_settings(self.assistant.settings)
        name_entry.delete(0, "end")
        steps_entry.delete(0, "end")
        self._refresh_mission_list(list_frame)
        self._append_chat("System", f"Saved mission: {name}.")

    def _remove_mission_template(self, name: str, list_frame: ctk.CTkScrollableFrame) -> None:
        templates = [template for template in self._mission_templates() if str(template.get("name", "")).lower() != name.lower()]
        self.assistant.settings["mission_templates"] = templates
        save_settings(self.assistant.settings)
        self._refresh_mission_list(list_frame)
        self._append_chat("System", f"Removed mission: {name}.")

    def _start_mission(self, template: dict[str, Any]) -> None:
        if self.mission_running:
            self._append_chat("System", "A mission is already running. Let one dramatic operation finish at a time.")
            return
        name = str(template.get("name", "Mission"))
        steps = [str(step).strip() for step in template.get("steps", []) if str(step).strip()]
        if not steps:
            self._append_chat("System", f"Mission {name} has no steps.")
            return
        self.mission_running = True
        threading.Thread(target=self._mission_worker, args=(name, steps), daemon=True).start()

    def _mission_worker(self, name: str, steps: list[str]) -> None:
        self._set_status("Mission Running...")
        self._set_command_status(f"Mission: {name}")
        self._append_chat("System", f"Mission started: {name}. {len(steps)} step{'s' if len(steps) != 1 else ''}.")
        summary: list[str] = []
        try:
            for index, step in enumerate(steps, start=1):
                if self.assistant.pending_confirmation is not None:
                    summary.append(f"Stopped before step {index}: waiting for confirmation.")
                    break
                self._append_chat("System", f"Mission step {index}/{len(steps)}: {step}")
                role, response = self.assistant.handle_command(step)
                speaker = "JARVIS" if role in {"assistant", "action"} else "System"
                self._append_chat(speaker, response)
                summary.append(f"{index}. {step} -> {response[:120]}")
                if self.assistant.pending_confirmation is not None:
                    summary.append("Mission paused for confirmation.")
                    break
                time.sleep(0.5)
            else:
                summary.append("Mission completed.")
        except Exception as exc:
            summary.append(f"Mission error: {exc}")
        finally:
            final_text = f"Mission summary: {name}\n" + "\n".join(summary[-8:])
            self._append_chat("System", final_text)
            self.assistant.record_action(f"mission:{name}", {"steps": len(steps)}, "medium", "Mission error:" not in final_text, final_text, verified=True)
            self.mission_running = False
            self._set_status("Online")
            self._set_command_status("Mission complete")

    def _apply_window_icon(self, window: Any) -> None:
        icon_path = RESOURCE_DIR / "jarvis_icon.ico"
        if not icon_path.exists():
            icon_path = BASE_DIR / "jarvis_icon.ico"
        if not icon_path.exists():
            return
        try:
            window.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _accent_for_status_title(self, title: str) -> str:
        normalized = title.lower()
        if any(term in normalized for term in ("risk", "mouse", "permission")):
            return UI_AMBER
        if any(term in normalized for term in ("voice", "vision", "health", "vitals", "verified")):
            return UI_GREEN
        if any(term in normalized for term in ("music", "phone", "hand")):
            return UI_MAGENTA
        return UI_CYAN

    def _side_controls(self, parent: ctk.CTkFrame, row: int) -> None:
        frame = ctk.CTkFrame(parent, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
        frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(12, 6))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(
            frame,
            text="Controls",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=UI_CYAN,
        )
        label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(9, 4))

        buttons = [
            ("Apps", self.open_app_whitelist_window),
            ("Music", self.open_music_window),
            ("Memory", self.open_memory_window),
            ("Mic", self.open_microphone_window),
            ("News", self.open_news_panel),
            ("Video News", self.open_video_news_panel),
            ("Browser", self.open_browser_panel),
            ("Overlay", self.show_overlay),
            ("Watcher", self.open_project_watcher_window),
            ("Code", lambda: self._toggle_command_center_panel("code")),
            ("Missions", self.open_mission_dashboard_window),
            ("Hand Control", self.open_gesture_pad_window),
            ("Layouts", self.open_workspace_layout_window),
            ("Integrations", self.open_integrations_window),
            ("Panels", self.open_panel_manager_window),
        ]
        for index, (text, command) in enumerate(buttons):
            button = ctk.CTkButton(frame, text=text, height=30, fg_color=UI_CARD_ALT, hover_color=UI_BORDER_SOFT, text_color=UI_TEXT, command=command)
            button.grid(
                row=1 + index // 2,
                column=index % 2,
                sticky="ew",
                padx=(12 if index % 2 == 0 else 5, 12 if index % 2 == 1 else 5),
                pady=(4, 8 if index >= len(buttons) - 2 else 4),
            )

    def _core_status_card(self, parent: ctk.CTkFrame, title: str, variable: ctk.StringVar, row: int) -> None:
        accent = self._accent_for_status_title(title)
        frame = ctk.CTkFrame(parent, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
        frame.grid(row=row, column=0, sticky="ew", pady=(0 if row == 0 else 10, 10))
        frame.grid_columnconfigure(1, weight=1)
        accent_bar = ctk.CTkFrame(frame, fg_color=accent, corner_radius=5, width=4)
        accent_bar.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(8, 0), pady=10)
        label = ctk.CTkLabel(frame, text=title, anchor="w", font=ctk.CTkFont(size=11, weight="bold"), text_color=accent)
        label.grid(row=0, column=1, sticky="ew", padx=10, pady=(9, 0))
        value = ctk.CTkLabel(frame, textvariable=variable, anchor="w", justify="left", wraplength=245, text_color=UI_TEXT)
        value.grid(row=1, column=1, sticky="ew", padx=10, pady=(1, 10))

    def _side_label(self, parent: ctk.CTkFrame, title: str, variable: ctk.StringVar, row: int) -> None:
        accent = self._accent_for_status_title(title)
        frame = ctk.CTkFrame(parent, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
        frame.grid(row=row, column=0, sticky="ew", padx=12, pady=(12 if row == 0 else 6, 6))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkFrame(frame, fg_color=accent, corner_radius=4, width=3).grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(8, 0), pady=9)
        label = ctk.CTkLabel(frame, text=title.upper(), anchor="w", font=ctk.CTkFont(size=10, weight="bold"), text_color=accent)
        label.grid(row=0, column=1, sticky="ew", padx=10, pady=(8, 0))
        value = ctk.CTkLabel(frame, textvariable=variable, anchor="w", justify="left", wraplength=215, text_color=UI_TEXT)
        value.grid(row=1, column=1, sticky="ew", padx=10, pady=(2, 10))

    def open_browser_panel(self) -> None:
        self._set_command_center_panel_visible("browser", True)

    def _edge_executable(self) -> Path | None:
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        return next((path for path in candidates if path.is_file()), None)

    def _ensure_browser_home_page(self) -> Path:
        home_path = DATA_DIR / "jarvis_engine_home.html"
        home_html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Engine</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#030712;color:#e6fbff;
font-family:Segoe UI,Arial,sans-serif;display:grid;place-items:center;overflow:hidden}.grid{position:fixed;inset:0;
background-image:linear-gradient(#12384f55 1px,transparent 1px),linear-gradient(90deg,#12384f55 1px,transparent 1px);
background-size:64px 64px;opacity:.45}.core{position:relative;width:min(900px,88vw);text-align:center;padding:42px 28px}
.rings{position:absolute;left:50%;top:48%;width:520px;height:520px;translate:-50% -50%;border:1px solid #38bdf855;
border-radius:50%;animation:spin 18s linear infinite;pointer-events:none}.rings:before,.rings:after{content:"";position:absolute;
border-radius:50%;border:2px solid transparent}.rings:before{inset:42px;border-top-color:#76e4ff;border-bottom-color:#1d5f7a}
.rings:after{inset:108px;border-left-color:#70f0bf;border-right-color:#38bdf8;animation:spin 9s linear infinite reverse}
@keyframes spin{to{rotate:360deg}}.eyebrow{color:#70f0bf;font-size:12px;font-weight:700;letter-spacing:3px}
h1{font-size:clamp(44px,8vw,88px);margin:12px 0 4px;letter-spacing:4px;text-shadow:0 0 28px #38bdf866}
.sub{color:#8fb7c8;margin:0 0 34px;font-size:17px}.search{position:relative;display:flex;max-width:760px;margin:auto;
background:#07111fee;border:1px solid #1d5f7a;padding:8px;box-shadow:0 0 32px #38bdf822}.search input{flex:1;
min-width:0;border:0;outline:0;background:#06101c;color:#e6fbff;font-size:17px;padding:15px}.search button{border:0;
background:#1d5f7a;color:white;font-weight:700;padding:0 24px;cursor:pointer}.links{position:relative;display:flex;justify-content:center;
gap:10px;flex-wrap:wrap;margin-top:22px}.links a{color:#76e4ff;text-decoration:none;border:1px solid #12384f;background:#07111f;
padding:9px 14px}.links a:hover{border-color:#76e4ff}.status{margin-top:28px;color:#70f0bf;font-size:12px;letter-spacing:2px}
</style></head><body><div class="grid"></div><main class="core"><div class="rings"></div><div class="eyebrow">SYSTEM ONLINE</div>
<h1>JARVIS ENGINE</h1><p class="sub">Browse the web. I shall handle the dramatic lighting.</p>
<form class="search" action="https://www.google.com/search" method="get"><input name="q" autofocus autocomplete="off"
placeholder="Search the web with JARVIS Engine..."><button type="submit">SEARCH</button></form>
<nav class="links"><a href="https://news.google.com">News</a><a href="https://www.youtube.com">YouTube</a>
<a href="https://docs.google.com">Google Docs</a><a href="https://github.com">GitHub</a><a href="https://www.google.com/maps">Maps</a></nav>
<div class="status">CHROMIUM CORE READY</div></main></body></html>"""
        try:
            home_path.parent.mkdir(parents=True, exist_ok=True)
            if not home_path.exists() or home_path.read_text(encoding="utf-8", errors="ignore") != home_html:
                home_path.write_text(home_html, encoding="utf-8")
        except Exception:
            fallback = BASE_DIR / "jarvis_engine_home.html"
            fallback.write_text(home_html, encoding="utf-8")
            home_path = fallback
        return home_path

    def _ensure_browser_running(self) -> None:
        if self.browser_hwnd and ctypes.windll.user32.IsWindow(self.browser_hwnd):
            self._resize_embedded_browser()
            return
        edge = self._edge_executable()
        if edge is None:
            self.browser_status_var.set("Microsoft Edge is required for JARVIS Engine.")
            return
        home_path = self._ensure_browser_home_page()
        self.browser_home_url = home_path.as_uri()
        self.browser_address_var.set(self.browser_home_url)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.browser_debug_port = int(probe.getsockname()[1])
        profile = DATA_DIR / "jarvis_engine_profile"
        profile.mkdir(parents=True, exist_ok=True)
        command = [
            str(edge),
            f"--app={self.browser_home_url}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-session-crashed-bubble",
            "--disable-features=msEdgeSidebarV2,msEdgeShoppingAssistant",
            f"--remote-debugging-port={self.browser_debug_port}",
            f"--user-data-dir={profile}",
        ]
        try:
            self.browser_process = subprocess.Popen(command)
        except Exception as exc:
            self.browser_status_var.set(f"JARVIS Engine failed to start: {exc}")
            return
        self.browser_status_var.set("Starting Chromium core...")
        threading.Thread(target=self._wait_for_browser_window, args=(profile,), daemon=True).start()

    def _wait_for_browser_window(self, profile: Path) -> None:
        deadline = time.monotonic() + 18
        best_hwnd = 0
        while time.monotonic() < deadline:
            profile_text = str(profile).lower()
            pids: set[int] = set()
            for process in psutil.process_iter(["pid", "cmdline"]):
                try:
                    command_line = " ".join(process.info.get("cmdline") or []).lower()
                    if profile_text in command_line:
                        pids.add(int(process.info["pid"]))
                except Exception:
                    continue
            candidates: list[tuple[int, int, str]] = []
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

            @callback_type
            def enum_callback(hwnd: int, _lparam: int) -> bool:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if int(pid.value) not in pids:
                    return True
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buffer = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
                candidates.append((int(hwnd), area, buffer.value))
                return True

            ctypes.windll.user32.EnumWindows(enum_callback, 0)
            if candidates:
                named = [item for item in candidates if "jarvis engine" in item[2].lower()]
                chosen = max(named or candidates, key=lambda item: item[1])
                best_hwnd = chosen[0]
                if named or time.monotonic() + 3 >= deadline:
                    break
            time.sleep(0.35)
        if best_hwnd:
            self.after(0, lambda: self._embed_browser_window(best_hwnd))
        else:
            self.after(0, lambda: self.browser_status_var.set("Chromium started, but its window could not be mounted."))

    def _embed_browser_window(self, hwnd: int) -> None:
        surface = self.browser_surface
        if surface is None or not surface.winfo_exists():
            return
        surface.update_idletasks()
        user32 = ctypes.windll.user32
        get_window_long = user32.GetWindowLongPtrW
        set_window_long = user32.SetWindowLongPtrW
        get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        set_window_long.restype = ctypes.c_ssize_t
        style = int(get_window_long(hwnd, -16))
        style |= 0x40000000 | 0x02000000 | 0x04000000
        style &= ~(0x80000000 | 0x00C00000 | 0x00800000 | 0x00080000 | 0x00040000 | 0x00020000 | 0x00010000)
        set_window_long(hwnd, -16, style)
        ex_style = int(get_window_long(hwnd, -20))
        ex_style &= ~(0x08000000 | 0x00040000 | 0x00000200 | 0x00000100 | 0x00000080 | 0x00000001)
        set_window_long(hwnd, -20, ex_style)
        user32.SetParent(hwnd, surface.winfo_id())
        try:
            disabled = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(disabled), ctypes.sizeof(disabled))
        except Exception:
            pass
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0004 | 0x0002 | 0x0001)
        user32.ShowWindow(hwnd, 5)
        self.browser_hwnd = hwnd
        self.browser_status_var.set("JARVIS Engine online | Full Chromium browser")
        self._resize_embedded_browser()
        self._schedule_browser_focus_watch()

    def _schedule_browser_focus_watch(self) -> None:
        if self._browser_focus_watch_after is not None:
            return
        self._browser_focus_watch_after = self.after(45, self._watch_browser_focus)

    def _watch_browser_focus(self) -> None:
        self._browser_focus_watch_after = None
        user32 = ctypes.windll.user32
        mouse_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if mouse_down and not self._browser_mouse_down:
            point = ctypes.wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            surfaces = [
                (self.browser_hwnd, self.browser_surface, bool(self._session_panel_visibility.get("browser", False))),
                (self.video_player_hwnd, self.video_player_surface, bool(self._session_panel_visibility.get("video", False))),
            ]
            for hwnd, surface, panel_visible in surfaces:
                if not hwnd or surface is None or not panel_visible or not user32.IsWindow(hwnd):
                    continue
                left = surface.winfo_rootx()
                top = surface.winfo_rooty()
                right = left + surface.winfo_width()
                bottom = top + surface.winfo_height()
                if left <= point.x < right and top <= point.y < bottom:
                    target = int(user32.WindowFromPoint(point))
                    if target == hwnd or user32.IsChild(hwnd, target):
                        self._focus_embedded_browser(target)
                        break
        self._browser_mouse_down = mouse_down
        if self.winfo_exists():
            self._browser_focus_watch_after = self.after(45, self._watch_browser_focus)

    def _focus_embedded_browser(self, target_hwnd: int) -> None:
        user32 = ctypes.windll.user32
        target_thread = int(user32.GetWindowThreadProcessId(target_hwnd, None))
        current_thread = int(ctypes.windll.kernel32.GetCurrentThreadId())
        attached = False
        try:
            if target_thread and target_thread != current_thread:
                attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
            user32.SetForegroundWindow(self.winfo_id())
            user32.SetFocus(target_hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(current_thread, target_thread, False)

    def _toggle_browser_fill(self) -> None:
        current = self._panel_layout("browser")
        is_filled = current["relw"] >= 0.97 and current["relh"] >= 0.97
        if is_filled and self._browser_restore_layout is not None:
            self._session_panel_layout["browser"] = self._browser_restore_layout
            self._browser_restore_layout = None
            if self.browser_fill_button is not None:
                self.browser_fill_button.configure(text="Fill")
            self.browser_status_var.set("Browser panel restored")
        else:
            self._browser_restore_layout = current.copy()
            self._session_panel_layout["browser"] = {
                "relx": 0.005,
                "rely": 0.005,
                "relw": 0.99,
                "relh": 0.99,
            }
            if self.browser_fill_button is not None:
                self.browser_fill_button.configure(text="Restore")
            self.browser_status_var.set("Browser filled to workspace")
        self._place_command_panel("browser")
        self.after(80, self._resize_embedded_browser)

    def _resize_embedded_browser(self, _event: Any | None = None) -> None:
        self._apply_embedded_browser_size()
        if self._browser_resize_after is not None:
            try:
                self.after_cancel(self._browser_resize_after)
            except Exception:
                pass
        self._browser_resize_after = self.after(90, self._settle_embedded_browser_size)

    def _settle_embedded_browser_size(self) -> None:
        self._browser_resize_after = None
        self._apply_embedded_browser_size()

    def _apply_embedded_browser_size(self) -> None:
        if not self.browser_hwnd or self.browser_surface is None:
            return
        if not ctypes.windll.user32.IsWindow(self.browser_hwnd):
            self.browser_hwnd = 0
            return
        width = max(self.browser_surface.winfo_width(), 1)
        height = max(self.browser_surface.winfo_height(), 1)
        user32 = ctypes.windll.user32
        user32.SetWindowPos(self.browser_hwnd, 0, 0, 0, width, height, 0x0004 | 0x0010)
        user32.InvalidateRect(self.browser_hwnd, None, True)
        user32.UpdateWindow(self.browser_hwnd)

    def _browser_target(self) -> dict[str, Any] | None:
        if not self.browser_debug_port:
            return None
        try:
            targets = requests.get(f"http://127.0.0.1:{self.browser_debug_port}/json", timeout=3).json()
            pages = [item for item in targets if item.get("type") == "page" and item.get("webSocketDebuggerUrl")]
            normal_pages = [item for item in pages if not str(item.get("url", "")).startswith(("edge://", "devtools://"))]
            return (normal_pages or pages)[0] if pages else None
        except Exception:
            return None

    def _browser_command(self, method: str, params: dict[str, Any] | None, status: str) -> None:
        def worker() -> None:
            target = self._browser_target()
            if target is None or websockets is None:
                self.after(0, lambda: self.browser_status_var.set("Use the browser's native controls while the JARVIS link reconnects."))
                return

            async def send_command() -> None:
                async with websockets.connect(target["webSocketDebuggerUrl"], open_timeout=5) as connection:
                    await connection.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
                    while True:
                        response = json.loads(await connection.recv())
                        if response.get("id") == 1:
                            if response.get("error"):
                                raise RuntimeError(str(response["error"]))
                            return

            try:
                asyncio.run(send_command())
                self.after(0, lambda: self.browser_status_var.set(status))
            except Exception as exc:
                self.after(0, lambda: self.browser_status_var.set(f"Browser control unavailable: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _normalized_browser_url(self, value: str) -> str:
        value = value.strip()
        if not value:
            return self.browser_home_url
        if re.match(r"^(?:https?|file)://", value, re.IGNORECASE):
            return value
        if " " not in value and re.match(r"^(?:localhost|\d{1,3}(?:\.\d{1,3}){3}|[^/]+\.[a-z]{2,})(?:[/:].*)?$", value, re.IGNORECASE):
            return "https://" + value
        return "https://www.google.com/search?q=" + requests.utils.quote(value)

    def _browser_go(self) -> None:
        self._ensure_browser_running()
        url = self._normalized_browser_url(self.browser_address_var.get())
        self.browser_address_var.set(url)
        self._browser_command("Page.navigate", {"url": url}, "Navigation complete")

    def _browser_home(self) -> None:
        self._ensure_browser_running()
        if not self.browser_home_url:
            self.browser_home_url = self._ensure_browser_home_page().as_uri()
        self.browser_address_var.set(self.browser_home_url)
        self._browser_command("Page.navigate", {"url": self.browser_home_url}, "JARVIS Engine home")

    def _browser_history(self, direction: str) -> None:
        expression = "history.back()" if direction == "back" else "history.forward()"
        self._browser_command("Runtime.evaluate", {"expression": expression}, f"Browser {direction}")

    def _browser_reload(self) -> None:
        self._browser_command("Page.reload", {"ignoreCache": False}, "Page reloaded")

    def _open_browser_external(self) -> None:
        url = self._normalized_browser_url(self.browser_address_var.get())
        webbrowser.open(url)

    def _stop_browser_engine(self) -> None:
        profile_paths = {
            str(DATA_DIR / "jarvis_engine_profile").lower(),
            str(DATA_DIR / "jarvis_video_profile").lower(),
        }
        self.browser_hwnd = 0
        self.video_player_hwnd = 0
        for process in psutil.process_iter(["pid", "cmdline"]):
            try:
                command_line = " ".join(process.info.get("cmdline") or []).lower()
                if any(profile_path in command_line for profile_path in profile_paths):
                    process.terminate()
            except Exception:
                continue
        if self.video_player_server is not None:
            try:
                self.video_player_server.shutdown()
                self.video_player_server.server_close()
            except Exception:
                pass
            self.video_player_server = None

    def open_news_panel(self) -> None:
        self._set_command_center_panel_visible("news", True)

    def _switch_news_type(self, news_type: str) -> None:
        is_video = news_type == "Video"
        values = list(DEFAULT_VIDEO_NEWS_FEEDS.keys()) if is_video else list(DEFAULT_NEWS_FEEDS.keys())
        self.news_category_var.set(values[0])
        if self.news_category_menu is not None:
            self.news_category_menu.configure(values=values)
        self.refresh_news_panel()

    def open_video_news_panel(self) -> None:
        self.news_type_var.set("Video")
        values = list(DEFAULT_VIDEO_NEWS_FEEDS.keys())
        self.news_category_var.set(values[0])
        if self.news_category_menu is not None:
            self.news_category_menu.configure(values=values)
        self._set_command_center_panel_visible("news", True)

    def refresh_video_news_panel(self) -> None:
        frame = self.video_news_list_frame
        if frame is None:
            return
        channel = self.video_news_channel_var.get() or "Latest"
        self.video_news_status_var.set(f"Refreshing {channel}...")
        for child in frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(frame, text="Gathering video reports...", text_color=UI_TEXT, anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        def worker() -> None:
            items, status = fetch_video_news_items(channel)
            self.after(0, lambda: self._render_video_news_items(items, status))

        threading.Thread(target=worker, daemon=True).start()

    def _render_video_news_items(
        self,
        items: list[dict[str, str]],
        status: str,
        frame: ctk.CTkScrollableFrame | None = None,
        status_var: ctk.StringVar | None = None,
    ) -> None:
        frame = frame or self.video_news_list_frame
        if frame is None:
            return
        self.video_news_items = items
        (status_var or self.video_news_status_var).set(status)
        for child in frame.winfo_children():
            child.destroy()
        if not items:
            ctk.CTkLabel(frame, text=status, text_color=UI_TEXT, wraplength=420, justify="left").grid(row=0, column=0, sticky="ew", padx=14, pady=14)
            return
        for row, item in enumerate(items):
            card = ctk.CTkFrame(frame, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
            card.grid(row=row, column=0, sticky="ew", padx=10, pady=(10 if row == 0 else 6, 6))
            card.grid_columnconfigure(0, weight=1)
            source = str(item.get("source", "Video News")).strip()
            published = str(item.get("published", "")).strip()
            meta = source if not published else f"{source} | {published}"
            meta_label = ctk.CTkLabel(card, text=meta, text_color=UI_MAGENTA, anchor="w", font=ctk.CTkFont(size=10, weight="bold"))
            meta_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
            title_label = ctk.CTkLabel(card, text=f"VIDEO | {item.get('title', 'Untitled')}", text_color=UI_TEXT, anchor="w", justify="left", wraplength=380, font=ctk.CTkFont(size=14, weight="bold"))
            title_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(3, 10))
            ctk.CTkButton(card, text="View", width=68, height=30, fg_color=UI_BORDER, hover_color="#2898c5", command=lambda video=item: self.open_news_video(video)).grid(row=0, column=1, rowspan=2, padx=12, pady=12)
            for widget in (card, meta_label, title_label):
                widget.bind("<Button-1>", lambda _event, video=item: self.open_news_video(video))
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass

    def open_news_video(self, item: dict[str, str]) -> None:
        title = str(item.get("title", "Untitled video")).strip()
        source = str(item.get("source", "Video News")).strip()
        published = str(item.get("published", "")).strip()
        self.current_video_url = str(item.get("link", "")).strip()
        self.video_title_var.set(f"VIDEO | {title}")
        self.video_meta_var.set(source if not published else f"{source} | {published}")
        self.video_summary_var.set(str(item.get("summary", "")).strip() or "No description was provided for this report.")
        self.video_player_status_var.set("Preparing in-panel playback...")
        self._set_command_center_panel_visible("video", True)
        self.after(120, self._play_current_news_video)

    def _play_current_news_video(self) -> None:
        if not self.current_video_url:
            self.video_meta_var.set("Select a video headline first.")
            return
        video_id = self._youtube_video_id(self.current_video_url)
        if not video_id:
            self.video_player_status_var.set("This source cannot be embedded. Opening it in JARVIS Engine.")
            self.open_browser_panel()
            self.browser_address_var.set(self.current_video_url)
            self.after(400, self._browser_go)
            return
        player_url = self._video_player_url(video_id)
        if self.video_player_hwnd and ctypes.windll.user32.IsWindow(self.video_player_hwnd):
            self._video_player_navigate(player_url)
            return
        self._launch_video_player(player_url)

    def _open_current_news_video_external(self) -> None:
        if self.current_video_url:
            webbrowser.open(self.current_video_url)
        else:
            self.video_player_status_var.set("Select a video headline first.")

    def _youtube_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower().replace("www.", "")
        if host == "youtu.be":
            return parsed.path.strip("/").split("/", 1)[0]
        if host.endswith("youtube.com"):
            if parsed.path == "/watch":
                return str(parse_qs(parsed.query).get("v", [""])[0]).strip()
            match = re.search(r"/(?:embed|shorts|live)/([A-Za-z0-9_-]{6,})", parsed.path)
            if match:
                return match.group(1)
        return ""

    def _ensure_video_player_server(self) -> None:
        if self.video_player_server is not None:
            return
        player_path = DATA_DIR / "jarvis_video_player.html"
        player_html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS Video Player</title><style>html,body,#player{width:100%;height:100%;margin:0;background:#000;overflow:hidden}
body{font-family:Segoe UI,Arial,sans-serif}.error{display:grid;place-items:center;color:#76e4ff;height:100%;text-align:center}</style></head>
<body><div id="player"></div><script>
const id=new URLSearchParams(location.search).get('video');
if(!id){document.getElementById('player').innerHTML='<div class="error">No video selected.</div>';}else{
const frame=document.createElement('iframe');frame.width='100%';frame.height='100%';frame.frameBorder='0';
frame.allow='accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
frame.allowFullscreen=true;frame.src='https://www.youtube.com/embed/'+encodeURIComponent(id)+'?autoplay=1&controls=1&rel=0&playsinline=1&enablejsapi=1&origin='+encodeURIComponent(location.origin);
document.getElementById('player').appendChild(frame);}
</script></body></html>"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        player_path.write_text(player_html, encoding="utf-8")

        class QuietHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

        handler = partial(QuietHandler, directory=str(DATA_DIR))
        self.video_player_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.video_player_server.daemon_threads = True
        self.video_player_server_port = int(self.video_player_server.server_address[1])
        threading.Thread(target=self.video_player_server.serve_forever, daemon=True).start()

    def _video_player_url(self, video_id: str) -> str:
        self._ensure_video_player_server()
        return f"http://127.0.0.1:{self.video_player_server_port}/jarvis_video_player.html?video={requests.utils.quote(video_id)}"

    def _launch_video_player(self, player_url: str) -> None:
        edge = self._edge_executable()
        if edge is None:
            self.video_player_status_var.set("Microsoft Edge is required for in-panel video playback.")
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.video_player_debug_port = int(probe.getsockname()[1])
        profile = DATA_DIR / "jarvis_video_profile"
        profile.mkdir(parents=True, exist_ok=True)
        command = [
            str(edge),
            f"--app={player_url}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            "--disable-session-crashed-bubble",
            f"--remote-debugging-port={self.video_player_debug_port}",
            f"--user-data-dir={profile}",
        ]
        try:
            self.video_player_process = subprocess.Popen(command)
            self.video_player_status_var.set("Loading official video player...")
            threading.Thread(target=self._wait_for_video_player_window, args=(profile,), daemon=True).start()
        except Exception as exc:
            self.video_player_status_var.set(f"Video player failed to start: {exc}")

    def _wait_for_video_player_window(self, profile: Path) -> None:
        deadline = time.monotonic() + 18
        best_hwnd = 0
        while time.monotonic() < deadline:
            profile_text = str(profile).lower()
            pids: set[int] = set()
            for process in psutil.process_iter(["pid", "cmdline"]):
                try:
                    if profile_text in " ".join(process.info.get("cmdline") or []).lower():
                        pids.add(int(process.info["pid"]))
                except Exception:
                    continue
            candidates: list[tuple[int, int, str]] = []
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

            @callback_type
            def enum_callback(hwnd: int, _lparam: int) -> bool:
                if not ctypes.windll.user32.IsWindowVisible(hwnd):
                    return True
                pid = ctypes.wintypes.DWORD()
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if int(pid.value) not in pids:
                    return True
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buffer = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
                rect = ctypes.wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
                candidates.append((int(hwnd), area, buffer.value))
                return True

            ctypes.windll.user32.EnumWindows(enum_callback, 0)
            if candidates:
                named = [item for item in candidates if "jarvis video player" in item[2].lower()]
                chosen = max(named or candidates, key=lambda item: item[1])
                best_hwnd = chosen[0]
                if named or time.monotonic() + 3 >= deadline:
                    break
            time.sleep(0.35)
        if best_hwnd:
            self.after(0, lambda: self._embed_video_player_window(best_hwnd))
        else:
            self.after(0, lambda: self.video_player_status_var.set("Video started, but its player could not be mounted."))

    def _embed_video_player_window(self, hwnd: int) -> None:
        surface = self.video_player_surface
        if surface is None or not surface.winfo_exists():
            return
        surface.update_idletasks()
        user32 = ctypes.windll.user32
        get_window_long = user32.GetWindowLongPtrW
        set_window_long = user32.SetWindowLongPtrW
        get_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int]
        get_window_long.restype = ctypes.c_ssize_t
        set_window_long.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        set_window_long.restype = ctypes.c_ssize_t
        style = int(get_window_long(hwnd, -16))
        style |= 0x40000000 | 0x02000000 | 0x04000000
        style &= ~(0x80000000 | 0x00C00000 | 0x00800000 | 0x00080000 | 0x00040000 | 0x00020000 | 0x00010000)
        set_window_long(hwnd, -16, style)
        ex_style = int(get_window_long(hwnd, -20))
        ex_style &= ~(0x08000000 | 0x00040000 | 0x00000200 | 0x00000100 | 0x00000080 | 0x00000001)
        set_window_long(hwnd, -20, ex_style)
        user32.SetParent(hwnd, surface.winfo_id())
        try:
            disabled = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(disabled), ctypes.sizeof(disabled))
        except Exception:
            pass
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0020 | 0x0004 | 0x0002 | 0x0001)
        user32.ShowWindow(hwnd, 5)
        self.video_player_hwnd = hwnd
        self.video_player_status_var.set("Playing inside JARVIS")
        self._resize_embedded_video_player()
        self._schedule_browser_focus_watch()

    def _resize_embedded_video_player(self, _event: Any | None = None) -> None:
        hwnd = self.video_player_hwnd
        surface = self.video_player_surface
        if not hwnd or surface is None or not ctypes.windll.user32.IsWindow(hwnd):
            return
        width = max(surface.winfo_width(), 1)
        height = max(surface.winfo_height(), 1)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, width, height, 0x0004 | 0x0010)

    def _video_player_navigate(self, player_url: str) -> None:
        self.video_player_status_var.set("Loading selected report...")

        def worker() -> None:
            try:
                targets = requests.get(f"http://127.0.0.1:{self.video_player_debug_port}/json", timeout=3).json()
                target = next(
                    (item for item in targets if item.get("type") == "page" and item.get("webSocketDebuggerUrl")),
                    None,
                )
                if target is None or websockets is None:
                    raise RuntimeError("player control link unavailable")

                async def navigate() -> None:
                    async with websockets.connect(target["webSocketDebuggerUrl"], open_timeout=5) as connection:
                        await connection.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": player_url}}))
                        while True:
                            response = json.loads(await connection.recv())
                            if response.get("id") == 1:
                                if response.get("error"):
                                    raise RuntimeError(str(response["error"]))
                                return

                asyncio.run(navigate())
                self.after(0, lambda: self.video_player_status_var.set("Playing inside JARVIS"))
            except Exception as exc:
                self.after(0, lambda: self.video_player_status_var.set(f"Player navigation failed: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_news_panel(self) -> None:
        if self.news_list_frame is None:
            return
        category = self.news_category_var.get() or "Top Stories"
        news_type = self.news_type_var.get() or "Article"
        self._news_request_id += 1
        request_id = self._news_request_id
        self.news_status_var.set(f"Refreshing {news_type.lower()} news: {category}...")
        for child in self.news_list_frame.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.news_list_frame,
            text="Gathering video reports..." if news_type == "Video" else "Gathering article headlines...",
            text_color=UI_TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=12)

        def worker() -> None:
            if news_type == "Video":
                items, status = fetch_video_news_items(category)
                self.after(0, lambda: self._finish_main_news_refresh(request_id, news_type, items, status))
            else:
                items, status = fetch_news_items(category)
                self.after(0, lambda: self._finish_main_news_refresh(request_id, news_type, items, status))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_main_news_refresh(
        self,
        request_id: int,
        news_type: str,
        items: list[dict[str, str]],
        status: str,
    ) -> None:
        if request_id != self._news_request_id or news_type != self.news_type_var.get():
            return
        if news_type == "Video":
            self._render_video_news_items(items, status, self.news_list_frame, self.news_status_var)
        else:
            self._render_news_items(items, status)

    def _render_news_items(self, items: list[dict[str, str]], status: str) -> None:
        frame = self.news_list_frame
        if frame is None:
            return
        self.news_items = items
        self.news_status_var.set(status)
        for child in frame.winfo_children():
            child.destroy()
        if not items:
            ctk.CTkLabel(frame, text=status, text_color=UI_TEXT, wraplength=520, justify="left").grid(row=0, column=0, sticky="ew", padx=14, pady=14)
            return
        for row, item in enumerate(items):
            card = ctk.CTkFrame(frame, fg_color=UI_CARD, corner_radius=8, border_width=1, border_color=UI_BORDER_SOFT)
            card.grid(row=row, column=0, sticky="ew", padx=10, pady=(10 if row == 0 else 6, 6))
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)
            source = str(item.get("source", "News")).strip()
            published = str(item.get("published", "")).strip()
            meta = source if not published else f"{source} | {published}"
            meta_label = ctk.CTkLabel(card, text=meta, text_color=UI_GREEN, anchor="w", font=ctk.CTkFont(size=10, weight="bold"))
            meta_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
            title_label = ctk.CTkLabel(card, text=f"ARTICLE | {item.get('title', 'Untitled')}", text_color=UI_TEXT, anchor="w", justify="left", wraplength=380, font=ctk.CTkFont(size=14, weight="bold"))
            title_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(3, 0))
            clickable_widgets: list[Any] = [card, meta_label, title_label]
            summary = str(item.get("summary", "")).strip()
            if summary:
                summary_label = ctk.CTkLabel(card, text=summary, text_color=UI_MUTED, anchor="w", justify="left", wraplength=380)
                summary_label.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))
                clickable_widgets.append(summary_label)
            link = str(item.get("link", "")).strip()
            ctk.CTkButton(card, text="Read", width=68, height=30, fg_color=UI_BORDER, hover_color="#2898c5", command=lambda article=item: self.open_news_article(article)).grid(row=0, column=1, rowspan=3, padx=12, pady=12)
            for widget in clickable_widgets:
                widget.bind("<Button-1>", lambda _event, article=item: self.open_news_article(article))
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass

    def open_news_article(self, item: dict[str, str]) -> None:
        title = str(item.get("title", "Untitled article")).strip()
        source = str(item.get("source", "News")).strip()
        published = str(item.get("published", "")).strip()
        link = str(item.get("link", "")).strip()
        self.current_article_url = link
        self.article_title_var.set(title)
        self.article_meta_var.set(source if not published else f"{source} | {published}")
        self.article_status_var.set("Loading readable article...")
        self._set_article_text("JARVIS is retrieving the article. One moment.")
        self._set_command_center_panel_visible("article", True)
        self._set_command_status(f"Reading: {title[:48]}")

        def worker() -> None:
            article_text, status = fetch_news_article(item)
            self.after(0, lambda: self._finish_news_article(link, article_text, status))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_news_article(self, link: str, article_text: str, status: str) -> None:
        if link != self.current_article_url:
            return
        self.article_status_var.set(status)
        self._set_article_text(article_text or "No readable preview was available. Use Publisher to open the original article.")
        self._set_command_status("Article ready")

    def _set_article_text(self, text: str) -> None:
        if self.article_textbox is None:
            return
        self.article_textbox.configure(state="normal")
        self.article_textbox.delete("1.0", "end")
        self.article_textbox.insert("1.0", text)
        self.article_textbox.configure(state="disabled")
        self.article_textbox.yview_moveto(0.0)

    def _open_current_article_in_browser(self) -> None:
        if self.current_article_url:
            webbrowser.open(self.current_article_url)
        else:
            self.article_status_var.set("Select a headline first.")

    def show_overlay(self) -> None:
        if self.overlay_window is None or not self.overlay_window.winfo_exists():
            self._create_overlay()
        if self.overlay_window is None:
            return
        self.overlay_window.deiconify()
        self.overlay_window.lift()
        self.overlay_window.attributes("-topmost", True)
        if self.overlay_entry is not None:
            self.overlay_entry.focus_set()

    def hide_overlay(self) -> None:
        if self.overlay_window is not None and self.overlay_window.winfo_exists():
            self.overlay_window.withdraw()

    def show_main_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self._set_command_status("Command Center restored")

    def run_in_background(self, source: str = "main") -> None:
        message = "Running in the background. Ctrl+Alt+J brings up the overlay if the hotkey is available."
        self._append_chat("System", message)
        if source == "overlay":
            self._set_overlay_response(f"JARVIS: {message}")
        self._set_command_status("Background mode active")
        self.assistant.record_action("run_in_background", {}, "safe", True, message, verified=True)
        self.after(350, self.withdraw)

    def turn_off_all_instances(self, source: str = "main") -> None:
        message = "Shutting down all JARVIS instances. Finally, a little peace and quiet."
        self._append_chat("System", message)
        if source == "overlay":
            self._set_overlay_response(f"JARVIS: {message}")
        self._set_command_status("Shutting down JARVIS...")
        self.assistant.record_action("turn_off_jarvis", {}, "safe", True, message, verified=True)
        threading.Thread(target=self._terminate_other_jarvis_instances, daemon=True).start()
        self.after(450, self._on_close)

    def _terminate_other_jarvis_instances(self) -> None:
        current_pid = os.getpid()
        current_exe = str(Path(sys.executable).resolve()).lower()
        for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
            try:
                if int(proc.info.get("pid") or 0) == current_pid:
                    continue
                name = str(proc.info.get("name") or "").lower()
                exe = str(proc.info.get("exe") or "").lower()
                cmdline = " ".join(str(part).lower() for part in (proc.info.get("cmdline") or []))
                looks_like_packaged_app = "jarvis desktop assistant" in name or "jarvis desktop assistant" in exe
                looks_like_this_exe = bool(current_exe and exe == current_exe)
                looks_like_script = "jarvis.py" in cmdline and "python" in name
                if looks_like_packaged_app or looks_like_this_exe or looks_like_script:
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def _create_overlay(self) -> None:
        window = ctk.CTkToplevel(self)
        self.overlay_window = window
        window.title("J.A.R.V.I.S. Overlay")
        self._apply_window_icon(window)
        window.geometry("560x240+80+80")
        window.minsize(460, 210)
        window.configure(fg_color="#050812")
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(window, fg_color="#07111f", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="J.A.R.V.I.S.",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#8be9ff",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        ctk.CTkLabel(
            header,
            textvariable=self.command_var,
            font=ctk.CTkFont(size=11),
            text_color="#32d3ff",
        ).grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))
        ctk.CTkButton(header, text="Main", width=58, command=self.show_main_window).grid(row=0, column=1, rowspan=2, padx=(10, 4), pady=8)
        ctk.CTkButton(header, text="Hide", width=58, command=self.hide_overlay).grid(row=0, column=2, rowspan=2, padx=(4, 10), pady=8)

        body = ctk.CTkFrame(window, fg_color="#081525", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        self.overlay_entry = ctk.CTkEntry(body, placeholder_text="Type to JARVIS...", height=38)
        self.overlay_entry.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=(12, 6))
        self.overlay_entry.bind("<Return>", lambda _event: self.send_overlay_text())
        ctk.CTkButton(body, text="Send", width=72, command=self.send_overlay_text).grid(row=0, column=1, padx=6, pady=(12, 6))
        ctk.CTkButton(body, text="Voice", width=72, command=self.listen_once).grid(row=0, column=2, padx=(6, 12), pady=(12, 6))
        self.overlay_response_box = ctk.CTkTextbox(
            body,
            wrap="word",
            height=110,
            font=ctk.CTkFont(size=13),
            fg_color="#09101d",
            text_color="#d9f7ff",
        )
        self.overlay_response_box.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=12, pady=(0, 12))
        self.overlay_response_box.insert("1.0", "JARVIS: Ready.")
        self.overlay_response_box.configure(state="disabled")

    def _set_overlay_response(self, text: str) -> None:
        def write() -> None:
            self.overlay_response_var.set(text)
            if self.overlay_response_box is None or not self.overlay_response_box.winfo_exists():
                return
            self.overlay_response_box.configure(state="normal")
            self.overlay_response_box.delete("1.0", "end")
            self.overlay_response_box.insert("1.0", text)
            self.overlay_response_box.see("1.0")
            self.overlay_response_box.configure(state="disabled")

        self.after(0, write)

    def send_overlay_text(self) -> None:
        if self.overlay_entry is None:
            return
        text = self.overlay_entry.get().strip()
        if not text:
            return
        self.overlay_entry.delete(0, "end")
        self._set_overlay_response(f"You: {text}")
        self._submit_text(text, source="overlay")

    def open_microphone_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Microphone Input")
        self._apply_window_icon(window)
        window.geometry("680x520")
        window.minsize(560, 420)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Microphone Input",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))

        selected_index = self.assistant.settings.get("voice_input_device_index")
        selected_text = get_input_device_label(selected_index if isinstance(selected_index, int) else None)
        selected_var = ctk.StringVar(value=f"Selected: {selected_text}")
        selected_label = ctk.CTkLabel(window, textvariable=selected_var, text_color="#d9f7ff", anchor="w")
        selected_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        controls = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        controls.grid_columnconfigure(2, weight=1)
        test_button = ctk.CTkButton(
            controls,
            text="Test Selected",
            width=130,
            command=lambda: self._test_selected_microphone(selected_var),
        )
        test_button.grid(row=0, column=0, padx=10, pady=10)
        auto_button = ctk.CTkButton(
            controls,
            text="Auto Detect",
            width=120,
            command=lambda: self._auto_detect_microphone(list_frame, selected_var),
        )
        auto_button.grid(row=0, column=1, padx=(0, 10), pady=10)
        ctk.CTkLabel(
            controls,
            text="Speak while testing. Peaks under 250 usually mean the wrong mic.",
            text_color="#8ca9ba",
            anchor="w",
        ).grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=10)

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        list_frame.grid_columnconfigure(0, weight=1)
        self._refresh_microphone_list(list_frame, selected_var)

    def _refresh_microphone_list(self, list_frame: ctk.CTkScrollableFrame, selected_var: ctk.StringVar) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        devices = list_input_devices()
        if not devices:
            empty = ctk.CTkLabel(list_frame, text="No microphone input devices found.", text_color="#d9f7ff", anchor="w")
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        selected = self.assistant.settings.get("voice_input_device_index")
        for row, device in enumerate(devices):
            item = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
            item.grid_columnconfigure(0, weight=1)
            marker = "Selected" if selected == device["index"] else "Available"
            text = f"{device['index']}. {device['name']}\n{device['sample_rate']} Hz, {device['channels']} input channel(s) - {marker}"
            label = ctk.CTkLabel(item, text=text, anchor="w", justify="left", text_color="#eefbff")
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            select = ctk.CTkButton(
                item,
                text="Use",
                width=72,
                command=lambda index=device["index"]: self._select_microphone(index, list_frame, selected_var),
            )
            select.grid(row=0, column=1, padx=10, pady=8)

    def _select_microphone(self, device_index: int, list_frame: ctk.CTkScrollableFrame, selected_var: ctk.StringVar) -> None:
        self.assistant.settings["voice_input_device_index"] = device_index
        save_settings(self.assistant.settings)
        selected_var.set(f"Selected: {get_input_device_label(device_index)}")
        self._refresh_microphone_list(list_frame, selected_var)
        self._append_chat("System", f"Microphone set to {get_input_device_label(device_index)}.")

    def _test_selected_microphone(self, selected_var: ctk.StringVar) -> None:
        def worker() -> None:
            configured_index = self.assistant.settings.get("voice_input_device_index")
            device_index = configured_index if isinstance(configured_index, int) else None
            self._append_chat("System", f"Testing {get_input_device_label(device_index)} for 3 seconds. Speak now.")
            self._set_command_status("Testing microphone...")
            try:
                result = measure_microphone_level(device_index, seconds=3.0)
                message = f"Mic test peak: {result['peak']}/32767, RMS: {result['rms']}."
                if result["peak"] < 250:
                    message += " That is basically silence; try Auto Detect or another device."
                elif result["peak"] < 1800:
                    message += " Quiet, but usable with boosting."
                else:
                    message += " Good signal."
                self._append_chat("System", message)
                selected_var.set(f"Selected: {get_input_device_label(device_index)}")
            except Exception as exc:
                self._append_chat("System", f"Microphone test failed: {exc}")
            finally:
                self._set_command_status("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def _auto_detect_microphone(self, list_frame: ctk.CTkScrollableFrame, selected_var: ctk.StringVar) -> None:
        def worker() -> None:
            devices = list_input_devices()
            if not devices:
                self._append_chat("System", "No microphone input devices found.")
                return
            self._append_chat("System", "Auto detecting microphones. Speak normally for the next few seconds.")
            self._set_command_status("Auto detecting microphone...")
            best: dict[str, Any] | None = None
            for device in devices:
                try:
                    self._set_mic_status(f"Testing mic {device['index']}")
                    result = measure_microphone_level(device["index"], seconds=1.2)
                    self._append_chat("System", f"Mic {device['index']} peak: {result['peak']}/32767 - {device['name']}")
                    if best is None or result["peak"] > best["peak"]:
                        best = result
                except Exception as exc:
                    self._append_chat("System", f"Mic {device['index']} failed test: {exc}")
            if best is not None:
                self.assistant.settings["voice_input_device_index"] = int(best["device_index"])
                save_settings(self.assistant.settings)
                selected_var.set(f"Selected: {get_input_device_label(int(best['device_index']))}")
                self._refresh_microphone_list(list_frame, selected_var)
                self._append_chat(
                    "System",
                    f"Auto selected {best['device_index']}: {best['device_name']} with peak {best['peak']}/32767.",
                )
            self._set_mic_status("Ready")
            self._set_command_status("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def open_project_watcher_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Project Watcher")
        self._apply_window_icon(window)
        window.geometry("760x520")
        window.minsize(620, 420)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Project Watcher",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        note = ctk.CTkLabel(
            window,
            text="Watch project folders for changed files containing errors, tracebacks, failed builds, and Godot-style parser complaints.",
            text_color="#d9f7ff",
            anchor="w",
            wraplength=700,
        )
        note.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        form = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        form.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        form.grid_columnconfigure(0, weight=1)
        folder_entry = ctk.CTkEntry(form, placeholder_text="Choose or paste a project folder path")
        folder_entry.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=12)
        browse = ctk.CTkButton(form, text="Browse", width=86, command=lambda: self._browse_watch_folder(folder_entry))
        browse.grid(row=0, column=1, padx=6, pady=12)
        list_frame = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        list_frame.grid_columnconfigure(0, weight=1)
        add = ctk.CTkButton(form, text="Watch", width=86, command=lambda: self._add_watch_folder_from_window(folder_entry, list_frame))
        add.grid(row=0, column=2, padx=(6, 12), pady=12)

        controls = ctk.CTkFrame(window, fg_color="transparent")
        controls.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        controls.grid_columnconfigure(0, weight=1)
        toggle_text = "Turn Off" if self.assistant.settings.get("project_watcher_enabled", True) else "Turn On"
        toggle = ctk.CTkButton(controls, text=toggle_text, width=96, command=lambda: self._toggle_project_watcher(toggle))
        toggle.grid(row=0, column=1, sticky="e")
        self._refresh_watch_folders_list(list_frame)

    def _browse_watch_folder(self, folder_entry: ctk.CTkEntry) -> None:
        path = filedialog.askdirectory(title="Choose project folder")
        if path:
            folder_entry.delete(0, "end")
            folder_entry.insert(0, path)

    def _add_watch_folder_from_window(self, folder_entry: ctk.CTkEntry, list_frame: ctk.CTkScrollableFrame) -> None:
        path = normalize_watch_folder(folder_entry.get())
        if path is None:
            messagebox.showerror("JARVIS", "Choose a real folder first.")
            return
        folders = [str(folder) for folder in self.assistant.settings.get("project_watch_folders", [])]
        if str(path) not in folders:
            folders.append(str(path))
        self.assistant.settings["project_watch_folders"] = folders
        self.assistant.settings["project_watcher_enabled"] = True
        save_settings(self.assistant.settings)
        folder_entry.delete(0, "end")
        self._refresh_watch_folders_list(list_frame)
        self._append_chat("System", f"Watching project folder: {path}.")

    def _remove_watch_folder_from_window(self, folder: str, list_frame: ctk.CTkScrollableFrame) -> None:
        folders = [str(path) for path in self.assistant.settings.get("project_watch_folders", []) if str(path) != folder]
        self.assistant.settings["project_watch_folders"] = folders
        save_settings(self.assistant.settings)
        self._refresh_watch_folders_list(list_frame)
        self._append_chat("System", f"Stopped watching: {folder}.")

    def _toggle_project_watcher(self, button: ctk.CTkButton) -> None:
        enabled = not bool(self.assistant.settings.get("project_watcher_enabled", True))
        self.assistant.settings["project_watcher_enabled"] = enabled
        save_settings(self.assistant.settings)
        button.configure(text="Turn Off" if enabled else "Turn On")
        self._append_chat("System", f"Project watcher {'enabled' if enabled else 'disabled'}.")

    def _refresh_watch_folders_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()
        folders = [str(folder) for folder in self.assistant.settings.get("project_watch_folders", [])]
        if not folders:
            empty = ctk.CTkLabel(list_frame, text="No watched project folders yet.", text_color="#d9f7ff", anchor="w")
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return
        for row, folder in enumerate(folders):
            item = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
            item.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(item, text=folder, anchor="w", justify="left", wraplength=560, text_color="#eefbff")
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            remove = ctk.CTkButton(item, text="Remove", width=80, command=lambda path=folder: self._remove_watch_folder_from_window(path, list_frame))
            remove.grid(row=0, column=1, padx=10, pady=8)

    def open_memory_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("JARVIS Memories")
        self._apply_window_icon(window)
        window.geometry("640x520")
        window.minsize(540, 420)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Saved Memories",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        note = ctk.CTkLabel(
            window,
            text="Only explicit memories are saved. Chat messages are not stored.",
            text_color="#d9f7ff",
            anchor="w",
        )
        note.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        body = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        body.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        form.grid_columnconfigure(0, weight=1)
        memory_entry = ctk.CTkEntry(form, placeholder_text="Example: I prefer synthwave when coding")
        memory_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        list_frame = ctk.CTkScrollableFrame(body, fg_color="#0c1d31", corner_radius=6)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        list_frame.grid_columnconfigure(0, weight=1)
        add_button = ctk.CTkButton(
            form,
            text="Add Memory",
            width=110,
            command=lambda: self._add_memory_from_window(memory_entry, list_frame),
        )
        add_button.grid(row=0, column=1)
        memory_entry.bind("<Return>", lambda _event: self._add_memory_from_window(memory_entry, list_frame))
        self._refresh_memory_list(list_frame)

    def _add_memory_from_window(self, memory_entry: ctk.CTkEntry, list_frame: ctk.CTkScrollableFrame) -> None:
        fact = memory_entry.get().strip()
        if not fact:
            return
        response = self.assistant.save_memory_fact(fact)
        memory_entry.delete(0, "end")
        self._refresh_memory_list(list_frame)
        self._append_chat("System", response)

    def _remove_memory_by_id(self, memory_id: str, list_frame: ctk.CTkScrollableFrame) -> None:
        self.assistant.memories = [memory for memory in self.assistant.memories if memory.get("id") != memory_id]
        save_memories(self.assistant.memories)
        self._refresh_memory_list(list_frame)
        self._append_chat("System", "Removed saved memory.")

    def _refresh_memory_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        memories = self.assistant.memories
        if not memories:
            empty = ctk.CTkLabel(list_frame, text="No saved memories yet.", text_color="#d9f7ff", anchor="w")
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        for row, memory in enumerate(reversed(memories)):
            item = ctk.CTkFrame(list_frame, fg_color="#09101d", corner_radius=6)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
            item.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(item, text=str(memory.get("text", "")), anchor="w", justify="left", wraplength=450, text_color="#eefbff")
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            remove = ctk.CTkButton(
                item,
                text="Remove",
                width=80,
                command=lambda memory_id=str(memory.get("id", "")): self._remove_memory_by_id(memory_id, list_frame),
            )
            remove.grid(row=0, column=1, padx=10, pady=8)

    def open_music_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("JARVIS Music")
        self._apply_window_icon(window)
        window.geometry("680x620")
        window.minsize(600, 520)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Music Control",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        note = ctk.CTkLabel(
            window,
            text="Tune how JARVIS searches, selects, and plays music. Exact playback still depends on what Apple Music exposes to Windows.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=620,
        )
        note.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        form = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        form.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Preferred app", text_color="#d9f7ff").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        preferred_var = ctk.StringVar(value=str(self.assistant.settings.get("preferred_music_app", "apple_music")))
        preferred_menu = ctk.CTkOptionMenu(
            form,
            values=["apple_music", "spotify", "youtube_music", "youtube"],
            variable=preferred_var,
            command=lambda value: self._set_music_setting("preferred_music_app", value, status_box),
        )
        preferred_menu.grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 6))

        ctk.CTkLabel(form, text="Apple result wait", text_color="#d9f7ff").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        wait_entry = ctk.CTkEntry(form, placeholder_text="Seconds, example: 4")
        wait_entry.insert(0, str(self.assistant.settings.get("apple_music_result_wait_seconds", 4)))
        wait_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=6)

        controls = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        controls.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        controls.grid_columnconfigure(0, weight=1)

        status_box = ctk.CTkTextbox(controls, height=150, wrap="word", fg_color="#09101d", text_color="#d9f7ff")
        status_box.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 10))
        status_box.configure(state="disabled")

        toggles = [
            ("Apple Music UI automation", "apple_music_ui_automation"),
            ("Vision play-button assist", "apple_music_use_vision_play_button"),
            ("Click verified Apple result", "apple_music_click_first_result"),
            ("Text-match result click", "apple_music_text_match_click"),
            ("Mobile Apple Music bridge", "mobile_apple_music_enabled"),
            ("Ask this device or mobile", "mobile_music_device_prompt"),
            ("Browser fallback", "music_open_browser_fallback"),
            ("Auto media play key after search", "auto_press_play_after_music_search"),
        ]
        for row, (label, key) in enumerate(toggles):
            var = ctk.BooleanVar(value=bool(self.assistant.settings.get(key, False)))
            switch = ctk.CTkSwitch(
                controls,
                text=label,
                variable=var,
                command=lambda setting_key=key, setting_var=var: self._set_music_setting(setting_key, bool(setting_var.get()), status_box),
            )
            switch.grid(row=row, column=0, sticky="w", padx=12, pady=(10 if row == 0 else 6, 4))

        action_row = ctk.CTkFrame(window, fg_color="transparent")
        action_row.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
        action_row.grid_columnconfigure(0, weight=1)
        save_wait = ctk.CTkButton(
            action_row,
            text="Save Wait",
            width=94,
            command=lambda: self._save_music_wait_seconds(wait_entry, status_box),
        )
        save_wait.grid(row=0, column=1, padx=6)
        test_query = ctk.CTkButton(
            action_row,
            text="Test Parser",
            width=104,
            command=lambda: self._show_music_parser_test(status_box),
        )
        test_query.grid(row=0, column=2, padx=6)
        refresh = ctk.CTkButton(
            action_row,
            text="Refresh",
            width=86,
            command=lambda: self._refresh_music_status_box(status_box),
        )
        refresh.grid(row=0, column=3, padx=6)
        phone_setup = ctk.CTkButton(
            action_row,
            text="Phone Bridge",
            width=112,
            command=self.open_phone_bridge_window,
        )
        phone_setup.grid(row=0, column=4, padx=6)

        self._refresh_music_status_box(status_box)

    def _set_music_setting(self, key: str, value: Any, status_box: ctk.CTkTextbox) -> None:
        self.assistant.settings[key] = value
        save_settings(self.assistant.settings)
        self._refresh_music_status_box(status_box)
        self.music_var.set(self._music_status())

    def _save_music_wait_seconds(self, wait_entry: ctk.CTkEntry, status_box: ctk.CTkTextbox) -> None:
        try:
            seconds = float(wait_entry.get().strip())
        except ValueError:
            messagebox.showerror("JARVIS", "Use a number of seconds. Even music requires time to obey physics.")
            return
        self.assistant.settings["apple_music_result_wait_seconds"] = max(1, min(10, seconds))
        save_settings(self.assistant.settings)
        self._refresh_music_status_box(status_box)

    def _show_music_parser_test(self, status_box: ctk.CTkTextbox) -> None:
        examples = [
            "play Master of Puppets by Metallica",
            "play michael jackson, pick any song",
            "play Bad by Michael Jackson on Apple Music",
        ]
        lines = ["Music parser examples:"]
        for example in examples:
            lines.append(f"- {example} -> {clean_music_query_text(example)}")
        self._write_textbox(status_box, "\n".join(lines))

    def _refresh_music_status_box(self, status_box: ctk.CTkTextbox) -> None:
        apps = detect_music_apps()
        lines = [
            "Music status:",
            f"Preferred app: {self.assistant.settings.get('preferred_music_app', 'apple_music')}",
            f"Apple Music: {'detected' if apps.get('apple_music') else 'not detected'}",
            f"Spotify: {'detected' if apps.get('spotify') else 'not detected'}",
            f"YouTube Music fallback: {'available' if apps.get('youtube_music') else 'off'}",
            f"Apple UI automation: {'on' if self.assistant.settings.get('apple_music_ui_automation', True) else 'off'}",
            f"Vision play-button assist: {'on' if self.assistant.settings.get('apple_music_use_vision_play_button', True) else 'off'}",
            f"Mobile Apple Music bridge: {'on' if self.assistant.settings.get('mobile_apple_music_enabled', True) else 'off'}",
            f"Ask this/mobile prompt: {'on' if self.assistant.settings.get('mobile_music_device_prompt', True) else 'off'}",
            f"Phone Bridge queue: {self.phone_queue.pending_count()} pending",
            f"Result wait: {self.assistant.settings.get('apple_music_result_wait_seconds', 4)} seconds",
        ]
        self._write_textbox(status_box, "\n".join(lines))

    def _write_textbox(self, textbox: ctk.CTkTextbox, text: str) -> None:
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.insert("end", text)
        textbox.configure(state="disabled")

    def open_integrations_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("JARVIS Integrations")
        self._apply_window_icon(window)
        window.geometry("820x680")
        window.minsize(700, 540)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Integrations",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
        note = ctk.CTkLabel(
            window,
            text="Enable free integrations here. API keys and tokens stay in .env; JARVIS will only show whether they are loaded.",
            text_color="#d9f7ff",
            anchor="w",
            justify="left",
            wraplength=760,
        )
        note.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))

        config_frame = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        config_frame.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        config_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(config_frame, text="Home Assistant URL", text_color="#d9f7ff").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        home_entry = ctk.CTkEntry(config_frame, placeholder_text="Example: http://homeassistant.local:8123")
        home_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=(12, 6))
        home_entry.insert(0, str(self.assistant.settings.get("home_assistant_url", "")))

        ctk.CTkLabel(config_frame, text="OBS WebSocket URL", text_color="#d9f7ff").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        obs_entry = ctk.CTkEntry(config_frame, placeholder_text="Example: ws://127.0.0.1:4455")
        obs_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=6)
        obs_entry.insert(0, str(self.assistant.settings.get("obs_websocket_url", "")))

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        list_frame.grid_columnconfigure(0, weight=1)

        save_button = ctk.CTkButton(
            config_frame,
            text="Save URLs",
            width=96,
            command=lambda: self._save_integration_urls(home_entry, obs_entry, list_frame),
        )
        save_button.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=12)

        self._refresh_integrations_list(list_frame)

    def _save_integration_urls(
        self,
        home_entry: ctk.CTkEntry,
        obs_entry: ctk.CTkEntry,
        list_frame: ctk.CTkScrollableFrame,
    ) -> None:
        self.assistant.settings["home_assistant_url"] = home_entry.get().strip()[:300]
        self.assistant.settings["obs_websocket_url"] = obs_entry.get().strip()[:300]
        save_settings(self.assistant.settings)
        self._refresh_integrations_list(list_frame)
        self._append_chat("System", "Integration URLs saved. Tokens still belong in .env, because I enjoy staying employed.")

    def _toggle_integration(self, key: str, enabled: bool, list_frame: ctk.CTkScrollableFrame) -> None:
        set_integration_enabled(self.assistant.settings, key, enabled)
        if key == "health_bridge":
            if enabled:
                self._restart_health_bridge()
            else:
                if self.health_bridge is not None:
                    self.health_bridge.stop()
                self.health_bridge = None
                self.health_var.set("Disabled")
        if key == "phone_bridge":
            if enabled:
                self._restart_phone_bridge()
            else:
                if self.phone_bridge is not None:
                    self.phone_bridge.stop()
                    self.phone_bridge = None
                self.phone_var.set("Disabled")
        self._refresh_integrations_list(list_frame)
        name = INTEGRATION_CATALOG.get(key, {}).get("name", key)
        state = "enabled" if enabled else "disabled"
        self._append_chat("System", f"{name} integration {state}.")

    def _open_integration_setup(self, key: str) -> None:
        if key == "health_bridge":
            self.open_health_bridge_window()
            return
        if key == "phone_bridge":
            self.open_phone_bridge_window()
            return
        url = str(INTEGRATION_CATALOG.get(key, {}).get("setup_url", "")).strip()
        if url:
            webbrowser.open(url)
            name = INTEGRATION_CATALOG.get(key, {}).get("name", key)
            self._append_chat("System", f"Opened setup docs for {name}.")

    def _refresh_integrations_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for key, meta in INTEGRATION_CATALOG.items():
            grouped.setdefault(str(meta.get("category", "Other")), []).append((key, meta))

        row = 0
        for category in sorted(grouped):
            category_label = ctk.CTkLabel(
                list_frame,
                text=category,
                text_color="#8be9ff",
                font=ctk.CTkFont(size=16, weight="bold"),
                anchor="w",
            )
            category_label.grid(row=row, column=0, sticky="ew", padx=10, pady=(12 if row else 8, 4))
            row += 1
            for key, meta in sorted(grouped[category], key=lambda item: str(item[1].get("name", item[0]))):
                enabled = integration_enabled(self.assistant.settings, key)
                status, detail = integration_status(key, self.assistant.settings)
                card = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6)
                card.grid(row=row, column=0, sticky="ew", padx=8, pady=5)
                card.grid_columnconfigure(0, weight=1)

                top_line = ctk.CTkFrame(card, fg_color="transparent")
                top_line.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(8, 2))
                top_line.grid_columnconfigure(0, weight=1)
                name_label = ctk.CTkLabel(
                    top_line,
                    text=f"{meta.get('name', key)}  -  {status}",
                    anchor="w",
                    text_color="#eefbff",
                    font=ctk.CTkFont(size=13, weight="bold"),
                )
                name_label.grid(row=0, column=0, sticky="ew")

                switch_var = ctk.BooleanVar(value=enabled)
                toggle = ctk.CTkSwitch(
                    top_line,
                    text="",
                    width=48,
                    variable=switch_var,
                    command=lambda item_key=key, var=switch_var: self._toggle_integration(item_key, bool(var.get()), list_frame),
                )
                toggle.grid(row=0, column=1, sticky="e", padx=(8, 0))

                body = f"{detail}\n{meta.get('notes', '')}"
                env_vars = [str(env_name) for env_name in meta.get("env", [])]
                if env_vars:
                    loaded = [name for name in env_vars if os.getenv(name)]
                    missing = [name for name in env_vars if not os.getenv(name)]
                    body += f"\n.env: loaded {len(loaded)}/{len(env_vars)}"
                    if missing:
                        body += f" | missing {', '.join(missing)}"
                detail_label = ctk.CTkLabel(card, text=body, anchor="w", justify="left", wraplength=610, text_color="#d9f7ff")
                detail_label.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))

                docs = ctk.CTkButton(card, text="Setup", width=78, command=lambda item_key=key: self._open_integration_setup(item_key))
                docs.grid(row=1, column=1, sticky="e", padx=(4, 10), pady=(2, 8))
                row += 1

    def open_app_whitelist_window(self) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Whitelisted Apps")
        self._apply_window_icon(window)
        window.geometry("720x720")
        window.minsize(620, 560)
        window.configure(fg_color="#050812")
        window.transient(self)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)
        window.grid_rowconfigure(5, weight=1)

        header = ctk.CTkLabel(
            window,
            text="Whitelisted Apps",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#8be9ff",
        )
        header.grid(row=0, column=0, sticky="w", padx=18, pady=(18, 8))

        form = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        form.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Name", text_color="#d9f7ff").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        name_entry = ctk.CTkEntry(form, placeholder_text="Example: Blender")
        name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=12, pady=(12, 6))

        ctk.CTkLabel(form, text="Path", text_color="#d9f7ff").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        path_entry = ctk.CTkEntry(form, placeholder_text="Choose an .exe or .lnk file")
        path_entry.grid(row=1, column=1, sticky="ew", padx=(12, 6), pady=6)
        browse_button = ctk.CTkButton(form, text="Browse", width=88, command=lambda: self._browse_app_path(path_entry))
        browse_button.grid(row=1, column=2, sticky="e", padx=(6, 12), pady=6)

        ctk.CTkLabel(form, text="Aliases", text_color="#d9f7ff").grid(row=2, column=0, sticky="w", padx=12, pady=(6, 12))
        alias_entry = ctk.CTkEntry(form, placeholder_text="Optional: comma-separated names like blender, b3d")
        alias_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=12, pady=(6, 12))

        action_row = ctk.CTkFrame(window, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
        action_row.grid_columnconfigure(0, weight=1)
        add_button = ctk.CTkButton(
            action_row,
            text="Add To Whitelist",
            command=lambda: self._add_custom_app(name_entry, path_entry, alias_entry, list_frame),
        )
        add_button.grid(row=0, column=1, sticky="e")

        list_frame = ctk.CTkScrollableFrame(window, fg_color="#081525", corner_radius=8)
        list_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
        list_frame.grid_columnconfigure(0, weight=1)
        self._refresh_custom_apps_list(list_frame)

        steam_header = ctk.CTkLabel(
            window,
            text="Steam Games",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#8be9ff",
        )
        steam_header.grid(row=4, column=0, sticky="w", padx=18, pady=(4, 6))

        steam_frame = ctk.CTkFrame(window, fg_color="#081525", corner_radius=8)
        steam_frame.grid(row=5, column=0, sticky="nsew", padx=18, pady=(0, 18))
        steam_frame.grid_columnconfigure(0, weight=1)
        steam_frame.grid_rowconfigure(1, weight=1)

        steam_form = ctk.CTkFrame(steam_frame, fg_color="transparent")
        steam_form.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        steam_form.grid_columnconfigure(0, weight=1)
        steam_form.grid_columnconfigure(1, weight=0)

        steam_name_entry = ctk.CTkEntry(steam_form, placeholder_text="Game name, example: Stardew Valley")
        steam_name_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        steam_id_entry = ctk.CTkEntry(steam_form, placeholder_text="Steam App ID, example: 413150", width=190)
        steam_id_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 8))
        steam_list_frame = ctk.CTkScrollableFrame(steam_frame, fg_color="#0c1d31", corner_radius=6)
        steam_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        steam_list_frame.grid_columnconfigure(0, weight=1)
        add_steam_button = ctk.CTkButton(
            steam_form,
            text="Add Game",
            width=92,
            command=lambda: self._add_steam_game(steam_name_entry, steam_id_entry, steam_list_frame),
        )
        add_steam_button.grid(row=0, column=2, sticky="e", pady=(0, 8))
        import_steam_button = ctk.CTkButton(
            steam_form,
            text="Import Library",
            width=112,
            command=lambda: self._import_steam_library_from_window(steam_list_frame),
        )
        import_steam_button.grid(row=1, column=0, columnspan=3, sticky="e")
        self._refresh_steam_games_list(steam_list_frame)

    def _browse_app_path(self, path_entry: ctk.CTkEntry) -> None:
        path = filedialog.askopenfilename(
            title="Choose app",
            filetypes=[
                ("Apps and shortcuts", "*.exe *.lnk"),
                ("Executables", "*.exe"),
                ("Shortcuts", "*.lnk"),
                ("All files", "*.*"),
            ],
        )
        if path:
            path_entry.delete(0, "end")
            path_entry.insert(0, path)

    def _add_custom_app(
        self,
        name_entry: ctk.CTkEntry,
        path_entry: ctk.CTkEntry,
        alias_entry: ctk.CTkEntry,
        list_frame: ctk.CTkScrollableFrame,
    ) -> None:
        name = name_entry.get().strip()
        app_path = path_entry.get().strip()
        aliases = [alias.strip() for alias in alias_entry.get().split(",") if alias.strip()]

        if not name:
            messagebox.showerror("JARVIS", "Give the app a name first.")
            return

        path = Path(app_path)
        if not path.exists() or path.suffix.lower() not in {".exe", ".lnk"}:
            messagebox.showerror("JARVIS", "Choose a real .exe or .lnk file. I know, security is terribly inconvenient.")
            return

        custom_apps = list(self.assistant.settings.get("custom_whitelisted_apps", []))
        custom_apps = [app for app in custom_apps if str(app.get("name", "")).lower() != name.lower()]
        custom_apps.append({"name": name, "path": str(path), "aliases": aliases})
        self.assistant.settings["custom_whitelisted_apps"] = custom_apps
        save_settings(self.assistant.settings)

        name_entry.delete(0, "end")
        path_entry.delete(0, "end")
        alias_entry.delete(0, "end")
        self._refresh_custom_apps_list(list_frame)
        self._append_chat("System", f"Added {name} to the app whitelist.")

    def _remove_custom_app(self, name: str, list_frame: ctk.CTkScrollableFrame) -> None:
        custom_apps = [
            app
            for app in self.assistant.settings.get("custom_whitelisted_apps", [])
            if str(app.get("name", "")).lower() != name.lower()
        ]
        self.assistant.settings["custom_whitelisted_apps"] = custom_apps
        save_settings(self.assistant.settings)
        self._refresh_custom_apps_list(list_frame)
        self._append_chat("System", f"Removed {name} from the app whitelist.")

    def _refresh_custom_apps_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        custom_apps = self.assistant.settings.get("custom_whitelisted_apps", [])
        if not custom_apps:
            empty = ctk.CTkLabel(list_frame, text="No custom apps yet.", text_color="#d9f7ff", anchor="w")
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        for row, app in enumerate(custom_apps):
            name = str(app.get("name", "Unnamed app"))
            path = str(app.get("path", ""))
            aliases = ", ".join(app.get("aliases", []))
            item = ctk.CTkFrame(list_frame, fg_color="#0c1d31", corner_radius=6)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
            item.grid_columnconfigure(0, weight=1)

            text = f"{name}\n{path}"
            if aliases:
                text += f"\nAliases: {aliases}"
            label = ctk.CTkLabel(item, text=text, anchor="w", justify="left", text_color="#eefbff")
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            remove = ctk.CTkButton(item, text="Remove", width=80, command=lambda app_name=name: self._remove_custom_app(app_name, list_frame))
            remove.grid(row=0, column=1, padx=10, pady=8)

    def _add_steam_game(
        self,
        name_entry: ctk.CTkEntry,
        app_id_entry: ctk.CTkEntry,
        list_frame: ctk.CTkScrollableFrame,
    ) -> None:
        name = name_entry.get().strip()
        app_id = app_id_entry.get().strip()
        if not name:
            messagebox.showerror("JARVIS", "Give the Steam game a name first.")
            return
        if not app_id.isdigit():
            messagebox.showerror("JARVIS", "Steam App IDs are numbers only. Tedious, but wonderfully unambiguous.")
            return

        steam_games = dict(self.assistant.settings.get("steam_games", {}))
        steam_games[name] = app_id
        self.assistant.settings["steam_games"] = steam_games
        save_settings(self.assistant.settings)
        name_entry.delete(0, "end")
        app_id_entry.delete(0, "end")
        self._refresh_steam_games_list(list_frame)
        self._append_chat("System", f"Added Steam game {name} with App ID {app_id}.")

    def _remove_steam_game(self, name: str, list_frame: ctk.CTkScrollableFrame) -> None:
        steam_games = dict(self.assistant.settings.get("steam_games", {}))
        steam_games.pop(name, None)
        self.assistant.settings["steam_games"] = steam_games
        save_settings(self.assistant.settings)
        self._refresh_steam_games_list(list_frame)
        self._append_chat("System", f"Removed Steam game {name}.")

    def _import_steam_library_from_window(self, list_frame: ctk.CTkScrollableFrame) -> None:
        added_count, imported = import_steam_library(self.assistant.settings)
        self._refresh_steam_games_list(list_frame)
        if not imported:
            messagebox.showinfo("JARVIS", "I couldn't find installed Steam game manifests.")
            return
        self._append_chat(
            "System",
            f"Imported {len(imported)} installed Steam games from Steam. {added_count} were new.",
        )

    def _refresh_steam_games_list(self, list_frame: ctk.CTkScrollableFrame) -> None:
        for child in list_frame.winfo_children():
            child.destroy()

        steam_games = self.assistant.settings.get("steam_games", {})
        if not steam_games:
            empty = ctk.CTkLabel(
                list_frame,
                text="No Steam games yet. Add a game name and Steam App ID.",
                text_color="#d9f7ff",
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
            return

        for row, (name, app_id) in enumerate(sorted(steam_games.items(), key=lambda item: item[0].lower())):
            item = ctk.CTkFrame(list_frame, fg_color="#09101d", corner_radius=6)
            item.grid(row=row, column=0, sticky="ew", padx=8, pady=6)
            item.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(
                item,
                text=f"{name}\nSteam App ID: {app_id}",
                anchor="w",
                justify="left",
                text_color="#eefbff",
            )
            label.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
            remove = ctk.CTkButton(item, text="Remove", width=80, command=lambda game_name=name: self._remove_steam_game(game_name, list_frame))
            remove.grid(row=0, column=1, padx=10, pady=8)

    def _show_boot_screen(self) -> None:
        self.boot_frame = ctk.CTkFrame(self, fg_color="#020611", corner_radius=0)
        self.boot_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.boot_frame.lift()
        self.boot_frame.bind("<Button-1>", lambda _event: self._finish_boot_screen())

        self.boot_canvas = ctk.CTkCanvas(self.boot_frame, bg="#020611", highlightthickness=0)
        self.boot_canvas.pack(fill="both", expand=True)
        self.boot_canvas.bind("<Button-1>", lambda _event: self._finish_boot_screen())
        self.boot_step = 0
        self._animate_boot_screen()

    def _animate_boot_screen(self) -> None:
        if self.boot_canvas is None or self.boot_frame is None:
            return

        canvas = self.boot_canvas
        width = max(canvas.winfo_width(), 900)
        height = max(canvas.winfo_height(), 600)
        step = self.boot_step
        progress = min(1.0, step / 72)
        pulse = 1 + (step % 18) / 18

        canvas.delete("all")
        canvas.create_rectangle(0, 0, width, height, fill="#020611", outline="")

        for x in range(0, width, 72):
            color = "#07111f" if x % 144 else "#0a2033"
            canvas.create_line(x, 0, x, height, fill=color)
        for y in range(0, height, 54):
            color = "#07111f" if y % 108 else "#0a2033"
            canvas.create_line(0, y, width, y, fill=color)

        scan_y = int((step * 11) % max(height, 1))
        canvas.create_rectangle(0, scan_y - 18, width, scan_y + 18, fill="#041d2d", outline="")
        canvas.create_line(0, scan_y, width, scan_y, fill="#17d9ff", width=2)

        center_x = width // 2
        center_y = height // 2 - 26
        ring_base = min(width, height) // 5
        for index, color in enumerate(["#0a6f99", "#12c8ff", "#8be9ff"]):
            radius = ring_base + index * 34 + int(pulse * 4)
            start = (step * (4 + index * 2)) % 360
            canvas.create_arc(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                start=start,
                extent=92 + index * 18,
                outline=color,
                width=2 + index,
                style="arc",
            )
            canvas.create_arc(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                start=start + 180,
                extent=52 + index * 15,
                outline="#115578",
                width=2,
                style="arc",
            )

        canvas.create_oval(center_x - 72, center_y - 72, center_x + 72, center_y + 72, outline="#1fdcff", width=2)
        canvas.create_oval(center_x - 36, center_y - 36, center_x + 36, center_y + 36, fill="#031523", outline="#8be9ff", width=2)
        canvas.create_oval(center_x - 12, center_y - 12, center_x + 12, center_y + 12, fill="#27d8ff", outline="#d9f7ff", width=1)

        canvas.create_text(center_x, 96, text="J.A.R.V.I.S.", fill="#c8f6ff", font=("Segoe UI", 44, "bold"))
        canvas.create_text(center_x, 142, text="SYSTEM BOOT SEQUENCE", fill="#32d3ff", font=("Segoe UI", 13, "bold"))

        status_messages = [
            "Initializing J.A.R.V.I.S.",
            "Voice system online",
            "Vision system online",
            "Mouse control set to safe mode",
            "Gemini connection established",
            "Systems are ready",
        ]
        message_index = min(len(status_messages) - 1, int(progress * len(status_messages)))
        canvas.create_text(center_x, center_y + ring_base + 98, text=status_messages[message_index], fill="#eefbff", font=("Segoe UI", 15))

        bar_width = min(560, width - 160)
        bar_x = center_x - bar_width // 2
        bar_y = center_y + ring_base + 126
        canvas.create_rectangle(bar_x, bar_y, bar_x + bar_width, bar_y + 14, outline="#17627f", fill="#04111c", width=2)
        canvas.create_rectangle(bar_x + 3, bar_y + 3, bar_x + 3 + int((bar_width - 6) * progress), bar_y + 11, fill="#1fdcff", outline="")
        canvas.create_text(center_x, bar_y + 40, text=f"{int(progress * 100):03d}% INITIALIZED", fill="#6edcff", font=("Consolas", 12, "bold"))

        left_x = max(42, center_x - bar_width // 2)
        readouts = [
            ("VOICE", "STANDBY"),
            ("GEMINI", "LINKING" if progress < 0.75 else "READY"),
            ("MUSIC", "ROUTED"),
            ("LOCAL OPS", "SAFE MODE"),
        ]
        for index, (label, value) in enumerate(readouts):
            y = height - 150 + index * 26
            canvas.create_text(left_x, y, text=f"{label:<10}", anchor="w", fill="#32d3ff", font=("Consolas", 12, "bold"))
            canvas.create_text(left_x + 132, y, text=value, anchor="w", fill="#d9f7ff", font=("Consolas", 12))

        right_x = min(width - 42, center_x + bar_width // 2)
        for index in range(6):
            block_height = 12 + ((step + index * 4) % 34)
            x = right_x - 160 + index * 24
            canvas.create_rectangle(x, height - 104 - block_height, x + 12, height - 104, fill="#0e86b5", outline="#1fdcff")

        if progress >= 1.0:
            self.after(280, self._finish_boot_screen)
            return

        self.boot_step += 1
        self.after(45, self._animate_boot_screen)

    def _finish_boot_screen(self) -> None:
        if self.boot_frame is not None:
            self.boot_frame.destroy()
        self.boot_frame = None
        self.boot_canvas = None
        self.after(150, self._ensure_user_profile)

    def _ensure_user_profile(self) -> None:
        if self.assistant.settings.get("profile_initialized", False):
            self._enable_layout_autosave()
            return
        dialog = ctk.CTkInputDialog(
            text="What should JARVIS call you?",
            title="JARVIS User Setup",
        )
        entered = dialog.get_input()
        if entered is None:
            self._append_chat("System", "User setup is incomplete. JARVIS will ask again next time.")
            self._enable_layout_autosave()
            return
        user_name = re.sub(r"[^A-Za-z0-9 ._'-]", "", entered).strip()[:40] or "Sir"
        self.assistant.settings["user_name"] = user_name
        self.assistant.settings["profile_initialized"] = True
        self.assistant.personality["user_name"] = user_name
        self.assistant.personality["startup_greeting_name"] = user_name
        save_settings(self.assistant.settings)
        save_personality(self.assistant.personality)
        self._append_chat("JARVIS", f"Identity profile configured. Welcome, {user_name}.")
        self._enable_layout_autosave()

    def _draw_orb(self, radius: int) -> None:
        if self.orb is None:
            return
        self.orb.delete("all")
        width = max(72, int(self.orb.winfo_width() or 260))
        height = max(72, int(self.orb.winfo_height() or 260))
        center_x = width // 2
        center_y = height // 2
        base = min(width, height) // 2
        pulse_radius = max(32, min(radius, base - 24))
        outer = base - 16
        mid = max(34, base - 39)
        inner = max(22, base - 72)

        self.orb.create_oval(center_x - outer, center_y - outer, center_x + outer, center_y + outer, outline=UI_BORDER_SOFT, width=2)
        for index in range(24):
            angle = math.radians(index * 15)
            tick_length = 10 if index % 3 == 0 else 5
            x1 = center_x + math.cos(angle) * (outer - tick_length)
            y1 = center_y + math.sin(angle) * (outer - tick_length)
            x2 = center_x + math.cos(angle) * outer
            y2 = center_y + math.sin(angle) * outer
            color = UI_CYAN if index % 3 == 0 else UI_BORDER_SOFT
            self.orb.create_line(x1, y1, x2, y2, fill=color, width=2 if index % 3 == 0 else 1)

        self.orb.create_arc(center_x - outer, center_y - outer, center_x + outer, center_y + outer, start=20, extent=118, outline=UI_BLUE, width=3, style="arc")
        self.orb.create_arc(center_x - outer + 10, center_y - outer + 10, center_x + outer - 10, center_y + outer - 10, start=204, extent=95, outline=UI_GREEN, width=2, style="arc")
        self.orb.create_arc(center_x - mid, center_y - mid, center_x + mid, center_y + mid, start=305, extent=82, outline=UI_MAGENTA, width=2, style="arc")
        self.orb.create_oval(center_x - pulse_radius, center_y - pulse_radius, center_x + pulse_radius, center_y + pulse_radius, outline=UI_BLUE, width=2)
        self.orb.create_oval(center_x - inner, center_y - inner, center_x + inner, center_y + inner, outline=UI_CYAN, width=2)
        self.orb.create_oval(center_x - 38, center_y - 38, center_x + 38, center_y + 38, outline="#b8f3ff", width=1)
        self.orb.create_oval(center_x - 15, center_y - 15, center_x + 15, center_y + 15, fill="#21d4ff", outline="#c8f7ff", width=1)
        self.orb.create_text(center_x, center_y + outer + 8, text="SYSTEMS ONLINE", fill=UI_MUTED, font=("Consolas", 9, "bold"))
        next_radius = 92 if radius <= 72 else 72
        self.after(500, lambda: self._draw_orb(next_radius))

    def _setup_microphone(self) -> None:
        self.microphone = None
        if sd is not None and np is not None:
            try:
                configured_index = self.assistant.settings.get("voice_input_device_index")
                device_index = configured_index if isinstance(configured_index, int) else None
                sd.check_input_settings(device=device_index, channels=1, dtype="int16")
                self.voice_backend = "sounddevice"
                self.mic_var.set("Ready")
                return
            except Exception as exc:
                self._append_chat("System", f"Default sounddevice microphone check failed: {exc}")
        try:
            self.microphone = sr.Microphone()
            self.voice_backend = "pyaudio"
            self.mic_var.set("Ready")
        except Exception as exc:
            self.voice_backend = "unavailable"
            self.mic_var.set("Unavailable")
            self._append_chat("System", f"Microphone unavailable: {exc}")

    def _setup_hotkey(self) -> None:
        if keyboard is None:
            return
        try:
            keyboard.add_hotkey("ctrl+space", lambda: self.after(0, self.interrupt_and_listen))
            keyboard.add_hotkey("ctrl+alt+j", lambda: self.after(0, self.show_overlay))
        except Exception:
            self._append_chat("System", "Global hotkeys unavailable. The Voice and Overlay buttons still work.")

    def _toggle_wake_listener(self) -> None:
        if self.wake_enabled_var.get():
            self.start_wake_listener()
        else:
            self.stop_wake_listener()

    def start_wake_listener(self) -> None:
        if sd is None or np is None:
            self.wake_enabled_var.set(False)
            self.assistant.settings["wake_listening_enabled"] = False
            save_settings(self.assistant.settings)
            self._append_chat("System", "Wake listening requires sounddevice and NumPy.")
            return
        if self._wake_thread is not None and self._wake_thread.is_alive():
            return
        self._wake_stop.clear()
        self._wake_pause.clear()
        self.assistant.settings["wake_listening_enabled"] = True
        save_settings(self.assistant.settings)
        self.wake_enabled_var.set(True)
        self._wake_thread = threading.Thread(target=self._wake_listener_worker, daemon=True)
        self._wake_thread.start()
        wake = str(self.assistant.settings.get("wake_phrase", "jarvis")).title()
        self._set_mic_status(f"Wake ready: {wake}")
        self._set_command_status(f"Wake listening enabled for '{wake}'")

    def stop_wake_listener(self) -> None:
        self._wake_stop.set()
        self.assistant.settings["wake_listening_enabled"] = False
        save_settings(self.assistant.settings)
        self.wake_enabled_var.set(False)
        if not self.is_listening:
            self._set_mic_status("Ready" if self.voice_backend != "unavailable" else "Unavailable")
        self._set_command_status("Wake listening disabled")

    def _wake_listener_worker(self) -> None:
        while not self._wake_stop.is_set():
            if self._wake_pause.is_set() or self.is_listening or self._tts_speaking.is_set():
                self._wake_stop.wait(0.2)
                continue
            try:
                audio = self._capture_wake_utterance()
                if audio is None or self._wake_stop.is_set() or self._wake_pause.is_set():
                    continue
                text = self._transcribe_wake_audio(audio).strip()
                if not text:
                    self._set_command_status("Wake standby: no wake phrase recognized")
                    continue
                followup = time.monotonic() <= self._wake_followup_until
                detected, command = self._extract_wake_command(text)
                if not detected and not followup:
                    alternate = self._retry_wake_transcription_with_gemini(audio, text)
                    if alternate:
                        detected, command = self._extract_wake_command(alternate)
                        if detected:
                            text = alternate
                if followup and not detected:
                    detected = True
                    command = text.strip()
                if not detected:
                    self._set_command_status("Wake ready")
                    continue
                if not command:
                    self._wake_followup_until = time.monotonic() + 9.0
                    self._append_chat("You", str(self.assistant.settings.get("wake_phrase", "JARVIS")).upper())
                    self._append_chat("JARVIS", "Yes?")
                    if self.voice_enabled_var.get():
                        self.speak("Yes?")
                    continue
                self._wake_followup_until = 0.0
                self._append_chat("You", text)
                self._set_command_status(f"Wake command: {command[:80]}")
                self._process_command(command)
            except sr.UnknownValueError:
                self._set_command_status("Wake standby: speech was unclear")
            except Exception as exc:
                if not self._wake_stop.is_set():
                    self._append_chat("System", f"Wake listener paused after an audio error: {self._short_error_text(exc)}")
                    self._wake_stop.wait(2.0)
        if not self.is_listening:
            self._set_mic_status("Ready" if self.voice_backend != "unavailable" else "Unavailable")

    def _extract_wake_command(self, text: str) -> tuple[bool, str]:
        wake = str(self.assistant.settings.get("wake_phrase", "jarvis")).lower().strip()
        normalized = re.sub(r"[^a-z0-9' ]+", " ", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return False, ""
        if wake in normalized:
            return True, self.assistant._strip_wake_phrase(text).strip()

        tokens = normalized.replace("'", " ").split()
        aliases = {wake}
        if wake == "jarvis":
            aliases.update({"jervis", "charvis", "drivers", "service", "jarvises", "travis"})
        for index, token in enumerate(tokens):
            if index > 1:
                break
            score = difflib.SequenceMatcher(None, token, wake).ratio()
            if token in aliases or score >= 0.74:
                command_start = index + 1
                command = " ".join(tokens[command_start:]).strip()
                return True, command
        return False, ""

    def _retry_wake_transcription_with_gemini(self, audio: sr.AudioData, first_text: str) -> str:
        provider = str(self.assistant.settings.get("voice_transcription_provider", "auto")).lower()
        if provider != "auto" or len(first_text.split()) > 8 or self.assistant.gemini_client is None:
            return ""
        try:
            alternate = self.assistant.transcribe_audio_with_gemini(audio).strip()
            return alternate if alternate.lower() != first_text.lower() else ""
        except Exception:
            return ""
    def _transcribe_wake_audio(self, audio: sr.AudioData) -> str:
        provider = str(self.assistant.settings.get("voice_transcription_provider", "auto")).lower()
        if provider in {"auto", "google"}:
            try:
                return self.recognizer.recognize_google(audio).strip()
            except Exception:
                if provider == "google":
                    return ""
        if provider in {"auto", "gemini"}:
            try:
                return self.assistant.transcribe_audio_with_gemini(audio).strip()
            except Exception:
                return ""
        return ""
    def _capture_wake_utterance(self) -> sr.AudioData | None:
        configured_index = self.assistant.settings.get("voice_input_device_index")
        device_index = configured_index if isinstance(configured_index, int) else None
        device_info = sd.query_devices(device_index, kind="input") if device_index is not None else sd.query_devices(kind="input")
        sample_rate = int(float(device_info.get("default_samplerate", 44100)))
        wait_seconds = max(3, min(15, int(self.assistant.settings.get("wake_listening_timeout_seconds", 7))))
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata: np.ndarray, _frames: int, _time_info: Any, status: Any) -> None:
            if not status:
                audio_queue.put(indata.copy())

        chunks: list[np.ndarray] = []
        pre_roll: list[np.ndarray] = []
        pre_roll_samples = 0
        pre_roll_limit = int(sample_rate * 0.85)
        noise_peaks: list[int] = []
        speech_started = False
        active_run = 0
        voiced_samples = 0
        maximum_peak = 0
        last_threshold = 420
        silence_started = 0.0
        started = time.monotonic()
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=device_index,
            blocksize=max(512, min(2048, sample_rate // 30)),
            callback=callback,
        ):
            while not self._wake_stop.is_set() and not self._wake_pause.is_set():
                if time.monotonic() - started >= wait_seconds and not speech_started:
                    return None
                try:
                    chunk = audio_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                peak = int(np.max(np.abs(chunk))) if chunk.size else 0
                maximum_peak = max(maximum_peak, peak)
                pre_roll.append(chunk)
                pre_roll_samples += int(chunk.shape[0])
                while pre_roll and pre_roll_samples > pre_roll_limit:
                    removed = pre_roll.pop(0)
                    pre_roll_samples -= int(removed.shape[0])

                elapsed = time.monotonic() - started
                if elapsed < 0.55 and not speech_started:
                    noise_peaks.append(peak)
                    continue
                baseline = int(np.median(noise_peaks)) if noise_peaks else 80
                threshold = max(420, min(5000, baseline * 3 + 140))
                last_threshold = threshold
                if not speech_started:
                    if peak >= threshold:
                        active_run += 1
                    else:
                        active_run = 0
                    if active_run >= 2:
                        speech_started = True
                        chunks.extend(item.copy() for item in pre_roll)
                        voiced_samples += int(chunk.shape[0])
                        silence_started = 0.0
                    continue

                chunks.append(chunk)
                if peak >= int(threshold * 0.72):
                    voiced_samples += int(chunk.shape[0])
                if peak < int(threshold * 0.62):
                    if silence_started == 0.0:
                        silence_started = time.monotonic()
                    elif time.monotonic() - silence_started >= 1.05:
                        break
                else:
                    silence_started = 0.0
                if sum(item.shape[0] for item in chunks) >= sample_rate * 10:
                    break

        if not chunks:
            return None
        audio_array = np.concatenate(chunks).astype(np.int16).reshape(-1)
        raw_peak = int(np.max(np.abs(audio_array))) if audio_array.size else 0
        minimum_voiced_samples = int(sample_rate * 0.18)
        if raw_peak < max(500, int(last_threshold * 1.05)) or voiced_samples < minimum_voiced_samples:
            self._set_command_status("Wake standby: background noise ignored")
            return None
        audio_array, cleanup = clean_voice_audio(audio_array, sample_rate)
        padding = np.zeros(int(sample_rate * 0.22), dtype=np.int16)
        audio_array = np.concatenate((padding, audio_array, padding))
        duration = len(audio_array) / float(sample_rate)
        self._set_command_status(
            f"Wake speech captured: {duration:.1f}s, peak {cleanup['clean_peak']}/32767. Transcribing..."
        )
        return sr.AudioData(audio_array.tobytes(), sample_rate, 2)
    def _start_awareness_monitor(self) -> None:
        psutil.cpu_percent(interval=None)
        threading.Thread(target=self._awareness_monitor_worker, daemon=True).start()

    def _start_project_watcher(self) -> None:
        threading.Thread(target=self._project_watcher_worker, daemon=True).start()

    def _project_watcher_worker(self) -> None:
        while not self._project_watcher_stop.is_set():
            interval = int(self.assistant.settings.get("project_watch_interval_seconds", 10))
            interval = max(5, min(120, interval))
            try:
                if self.assistant.settings.get("project_watcher_enabled", True):
                    self._scan_project_watch_folders()
                else:
                    self.after(0, lambda: self.project_watcher_var.set("Paused"))
            except Exception as exc:
                self.after(0, lambda err=exc: self.project_watcher_var.set(f"Watcher error: {str(err)[:70]}"))
            self._project_watcher_stop.wait(interval)

    def _scan_project_watch_folders(self) -> None:
        folders = [normalize_watch_folder(str(folder)) for folder in self.assistant.settings.get("project_watch_folders", [])]
        folders = [folder for folder in folders if folder is not None]
        if not folders:
            self.after(0, lambda: self.project_watcher_var.set("No folders watched"))
            return

        scanned = 0
        changed = 0
        max_files_per_cycle = 450
        for folder in folders:
            try:
                paths = folder.rglob("*")
                for path in paths:
                    if scanned >= max_files_per_cycle:
                        break
                    if not is_watchable_project_file(path, self.assistant.settings):
                        continue
                    scanned += 1
                    try:
                        modified = path.stat().st_mtime
                    except OSError:
                        continue
                    key = str(path)
                    previous = self._watched_file_state.get(key)
                    self._watched_file_state[key] = modified
                    if previous is None:
                        continue
                    if modified <= previous:
                        continue
                    changed += 1
                    text = read_text_tail(path)
                    error_line = detect_error_in_text(text, self.assistant.settings)
                    if error_line:
                        self._emit_project_alert(path, error_line)
                if scanned >= max_files_per_cycle:
                    break
            except OSError:
                continue

        folder_word = "folder" if len(folders) == 1 else "folders"
        status = f"Watching {len(folders)} {folder_word} | scanned {scanned}"
        if changed:
            status += f" | changed {changed}"
        if scanned >= max_files_per_cycle:
            status += " | cycle capped"
        self.after(0, lambda text=status: self.project_watcher_var.set(text))

    def _emit_project_alert(self, path: Path, error_line: str) -> None:
        key = str(path)
        now = time.monotonic()
        cooldown = int(self.assistant.settings.get("monitor_alert_cooldown_seconds", 300))
        if now - self._last_project_alerts.get(key, 0) < cooldown:
            return
        self._last_project_alerts[key] = now
        message = f"Project watcher noticed an error in {path.name}: {error_line}"

        def deliver() -> None:
            self._append_chat("JARVIS", message)
            self._set_overlay_response(f"JARVIS: {message}")
            self._set_command_status(f"Project alert: {path.name}")
            if self.voice_enabled_var.get() and self.assistant.settings.get("proactive_speak_alerts", True):
                self.speak(message)

        self.after(0, deliver)

    def _awareness_monitor_worker(self) -> None:
        while not self._monitor_stop.is_set():
            interval = int(self.assistant.settings.get("monitor_interval_seconds", 12))
            interval = max(5, min(120, interval))
            try:
                snapshot = get_system_snapshot()
                self.after(0, lambda snap=snapshot: self._update_awareness_state(snap))
                if self.assistant.settings.get("proactive_monitoring_enabled", True):
                    self._evaluate_awareness_alerts(snapshot)
            except Exception as exc:
                self.after(0, lambda err=exc: self.awareness_var.set(f"Monitor error: {str(err)[:80]}"))
            self._monitor_stop.wait(interval)

    def _update_awareness_state(self, snapshot: dict[str, Any]) -> None:
        active_window = str(snapshot.get("active_window") or "Unknown")
        if active_window != self._active_window_last_title:
            self._active_window_last_title = active_window
            self._active_window_seen_at = time.monotonic()
            self._active_window_reminder_sent_for = ""

        elapsed_minutes = int((time.monotonic() - self._active_window_seen_at) / 60)
        enabled = bool(self.assistant.settings.get("proactive_monitoring_enabled", True))
        quiet = current_time_in_quiet_hours(self.assistant.settings)
        mode = "Quiet" if quiet else ("Watching" if enabled else "Paused")
        if elapsed_minutes >= 1:
            self.awareness_var.set(f"{mode} | {elapsed_minutes}m in current window")
        else:
            self.awareness_var.set(f"{mode} | current window tracked")
        self.monitor_summary_var.set(format_system_snapshot(snapshot))

    def _evaluate_awareness_alerts(self, snapshot: dict[str, Any]) -> None:
        cpu = float(snapshot.get("cpu") or 0)
        ram = float(snapshot.get("ram") or 0)
        disk = float(snapshot.get("disk") or 0)
        battery_percent = snapshot.get("battery_percent")
        battery_plugged = snapshot.get("battery_plugged")
        online = bool(snapshot.get("online"))

        cpu_limit = float(self.assistant.settings.get("cpu_alert_percent", 92))
        ram_limit = float(self.assistant.settings.get("ram_alert_percent", 90))
        disk_limit = float(self.assistant.settings.get("disk_alert_percent", 95))
        battery_limit = float(self.assistant.settings.get("battery_low_percent", 20))

        if cpu >= cpu_limit:
            self._emit_awareness_alert(
                "cpu_high",
                f"CPU is at {cpu:.0f}%. Something is breathing rather heavily in the machine room.",
            )
        if ram >= ram_limit:
            self._emit_awareness_alert(
                "ram_high",
                f"RAM usage is at {ram:.0f}%. Windows appears to be hoarding memory again.",
            )
        if disk >= disk_limit:
            self._emit_awareness_alert(
                "disk_high",
                f"Disk usage is at {disk:.0f}%. Storage is getting tight; even I need somewhere to put the clever remarks.",
            )
        if battery_percent is not None and battery_plugged is False and float(battery_percent) <= battery_limit:
            self._emit_awareness_alert(
                "battery_low",
                f"Battery is down to {float(battery_percent):.0f}% and you're unplugged. A charger would be the civilized move.",
            )

        self._evaluate_internet_alert(online)

        if self._last_battery_plugged is not None and battery_plugged is not None and battery_plugged != self._last_battery_plugged:
            state = "plugged in" if battery_plugged else "on battery"
            self._emit_awareness_alert("power_changed", f"Power state changed: laptop is now {state}.", force=True)
        if battery_plugged is not None:
            self._last_battery_plugged = bool(battery_plugged)

        reminder_minutes = int(self.assistant.settings.get("work_session_reminder_minutes", 90))
        if reminder_minutes > 0:
            elapsed_minutes = int((time.monotonic() - self._active_window_seen_at) / 60)
            active_window = str(snapshot.get("active_window") or "Unknown")
            reminder_key = f"{active_window}|{elapsed_minutes // reminder_minutes}"
            if elapsed_minutes >= reminder_minutes and self._active_window_reminder_sent_for != reminder_key:
                self._active_window_reminder_sent_for = reminder_key
                self._emit_awareness_alert(
                    "work_session",
                    f"You've been in {active_window} for about {elapsed_minutes} minutes. Stretching is still legal, sir.",
                )
        self._maybe_emit_context_suggestion(str(snapshot.get("active_window") or "Unknown"))

    def _evaluate_internet_alert(self, online: bool) -> None:
        if self._last_online_state is None:
            self._last_online_state = online
            self._online_success_streak = 1 if online else 0
            self._online_failure_streak = 0 if online else 1
            return

        failures_required = max(1, int(self.assistant.settings.get("internet_alert_failures_required", 3)))
        recoveries_required = max(1, int(self.assistant.settings.get("internet_alert_recoveries_required", 2)))

        if online:
            self._online_success_streak += 1
            self._online_failure_streak = 0
            if self._last_online_state is False and self._online_success_streak >= recoveries_required:
                self._last_online_state = True
                self._emit_awareness_alert(
                    "internet_restored",
                    "Internet connection is back online. I waited for confirmation this time; terribly mature of me.",
                    force=True,
                )
            return

        self._online_failure_streak += 1
        self._online_success_streak = 0
        if self._last_online_state is True and self._online_failure_streak >= failures_required:
            self._last_online_state = False
            self._emit_awareness_alert(
                "internet_lost",
                f"Internet connection appears to have dropped after {self._online_failure_streak} failed checks.",
                force=True,
            )

    def _maybe_emit_context_suggestion(self, active_window: str) -> None:
        if current_time_in_quiet_hours(self.assistant.settings):
            return
        lowered = active_window.lower()
        now = time.monotonic()
        suggestions = []
        if any(term in lowered for term in ["visual studio code", "code.exe", "vscode"]):
            suggestions.append(("vscode_focus", "You have been in VS Code for a while. Want me to start a focus timer?"))
        if "godot" in lowered:
            suggestions.append(("godot_notes", "Godot is active. I can open project notes if you want them."))
        if self._looks_like_writing_window(lowered):
            suggestions.append(
                (
                    "writing_assist",
                    "I see you're writing. Need a hand with dialogue, pacing, worldbuilding, or making a scene less suspiciously cooperative?",
                )
            )
        for key, message in suggestions:
            cooldown = self._context_suggestion_cooldown_seconds(key)
            if now - self._last_mode_suggestions.get(key, 0) > cooldown:
                self._last_mode_suggestions[key] = now
                self._emit_awareness_alert(key, message)

    def _looks_like_writing_window(self, lowered_title: str) -> bool:
        if not self.assistant.settings.get("writing_assist_prompt_enabled", True):
            return False
        lowered_title = lowered_title.lower()
        writing_terms = [
            "google docs",
            "docs.google.com",
            " - google docs",
            "google drive",
            "microsoft word",
            "word",
            ".docx",
            "novel",
            "manuscript",
            "chapter",
            "draft",
            "outline",
            "scrivener",
            "notion",
        ]
        browser_terms = ["chrome", "edge", "firefox", "brave", "opera"]
        if any(term in lowered_title for term in ["google docs", "docs.google.com", " - google docs"]):
            return True
        if any(term in lowered_title for term in writing_terms) and any(term in lowered_title for term in browser_terms + ["word", "scrivener", "notion"]):
            return True
        return False

    def _context_suggestion_cooldown_seconds(self, key: str) -> int:
        if key == "writing_assist":
            minutes = int(self.assistant.settings.get("writing_assist_prompt_cooldown_minutes", 45))
            return max(10, minutes * 60)
        return 1800

    def _emit_awareness_alert(self, key: str, message: str, force: bool = False) -> None:
        if current_time_in_quiet_hours(self.assistant.settings) and not force:
            return
        now = time.monotonic()
        cooldown = int(self.assistant.settings.get("monitor_alert_cooldown_seconds", 300))
        if not force and now - self._last_monitor_alerts.get(key, 0) < cooldown:
            return
        self._last_monitor_alerts[key] = now

        def deliver() -> None:
            self._append_chat("JARVIS", message)
            self._set_overlay_response(f"JARVIS: {message}")
            self._set_command_status(f"Alert: {message[:80]}")
            if self.voice_enabled_var.get() and self.assistant.settings.get("proactive_speak_alerts", True):
                self.speak(message)

        self.after(0, deliver)

    def _set_permission_mode(self, selected_mode: str, announce: bool = True) -> None:
        normalized = str(selected_mode).strip().lower()
        aliases = {
            "ask": "Ask for approval",
            "ask for approval": "Ask for approval",
            "approval": "Ask for approval",
            "approve": "Approve for me",
            "approve for me": "Approve for me",
            "automatic": "Approve for me",
            "full": "Full access",
            "full access": "Full access",
        }
        mode = aliases.get(normalized, selected_mode if selected_mode in PERMISSION_MODES else "Ask for approval")
        self.assistant.settings["agent_permission_mode"] = mode
        self.assistant.settings["agent_require_confirmation_for_medium"] = mode == "Ask for approval"
        self.permission_mode_var.set(mode)
        save_settings(self.assistant.settings)
        self.assistant.last_action = f"Permissions: {mode}"
        self.assistant.last_risk = "high" if mode == "Full access" else ("medium" if mode == "Approve for me" else "safe")
        descriptions = {
            "Ask for approval": "Medium and high-risk actions will ask first.",
            "Approve for me": "Safe and medium actions can run automatically; high-risk actions still ask first.",
            "Full access": "Approved tools can run automatically. Safe Mode still overrides this, and arbitrary terminal commands remain blocked.",
        }
        message = f"Permission mode set to {mode}. {descriptions[mode]}"
        self._set_command_status(message)
        if announce:
            self._append_chat("System", message)
            self._set_overlay_response(f"System: {message}")

    def _schedule_status_updates(self) -> None:
        self.window_var.set(get_active_window_title())
        self.time_var.set(dt.datetime.now().strftime("%I:%M %p").lstrip("0"))
        self.music_var.set(self._music_status())
        self.mode_var.set(self.assistant.current_mode)
        if self.phone_bridge is not None:
            status = self.phone_bridge.status()
            if status.running and self.phone_queue.pending_count():
                self.phone_var.set(f"Online: {self.phone_queue.pending_count()} queued")
        self.permission_mode_var.set(str(self.assistant.settings.get("agent_permission_mode", "Ask for approval")))
        self.vision_var.set("Online" if self.assistant.gemini_client is not None else "Offline")
        self.mouse_var.set(str(self.assistant.settings.get("mouse_control_mode", "Safe")))
        self.last_action_var.set(self.assistant.last_action)
        self.verified_action_var.set(self.assistant.last_verified_action)
        self.risk_var.set(str(self.assistant.last_risk).title())
        self.after(1500, self._schedule_status_updates)

    def _music_status(self) -> str:
        apps = detect_music_apps()
        detected = [name.replace("_", " ").title() for name, present in apps.items() if present]
        return ", ".join(detected) if detected else "Browser fallback"

    def send_text(self) -> None:
        text = self.input_entry.get().strip()
        if not text:
            return
        self.input_entry.delete(0, "end")
        self._submit_text(text, source="main")

    def _submit_text(self, text: str, source: str = "main") -> None:
        self._set_command_status(f"Already on it: {text[:70]}")
        self._append_chat("You", text)
        if source == "overlay":
            self._set_overlay_response(f"You: {text}\n\nJARVIS: Already on it.")
        if self._handle_app_ui_command(text, source):
            return
        threading.Thread(target=self._process_command, args=(text, source), daemon=True).start()

    def _handle_app_ui_command(self, text: str, source: str = "main") -> bool:
        lowered = text.lower().strip()
        permission_request = None
        if any(phrase in lowered for phrase in ["full access", "maximum access", "all permissions"]):
            permission_request = "Full access"
        elif any(phrase in lowered for phrase in ["approve for me", "auto approve", "automatic approval"]):
            permission_request = "Approve for me"
        elif any(phrase in lowered for phrase in ["ask for approval", "ask me first", "approval mode"]):
            permission_request = "Ask for approval"
        if permission_request and any(term in lowered for term in ["permission", "access", "approval", "mode", "set", "use", "switch"]):
            self._set_permission_mode(permission_request)
            return True
        if re.search(r"\b(?:open|show|launch|start)\s+(?:apple\s+)?health\s+(?:bridge|setup|panel)\b", lowered) or re.search(r"\b(?:health|watch)\s+setup\b", lowered):
            self.open_health_bridge_window()
            self._append_chat("System", "Apple Health Bridge setup opened.")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Apple Health Bridge setup opened.")
            return True
        if re.search(r"\b(?:open|show|launch|start)\s+(?:jarvis\s+)?phone\s+(?:bridge|setup|panel)\b", lowered) or re.search(r"\b(?:phone|iphone|mobile)\s+bridge\s+setup\b", lowered):
            self.open_phone_bridge_window()
            self._append_chat("System", "JARVIS Phone Bridge setup opened.")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Phone Bridge setup opened.")
            return True
        if re.search(r"\b(?:phone|iphone|mobile)\s+bridge\s+(?:status|queue)\b", lowered):
            message = self._latest_phone_status_text()
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:health|heart rate|apple watch|watch)\s+(?:status|reading|readings|update)\b", lowered) or lowered in {"health status", "heart rate", "apple watch status"}:
            message = self._latest_health_status_text()
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:enable|start|turn on|activate)\s+(?:apple\s+)?health\s+bridge\b", lowered):
            set_integration_enabled(self.assistant.settings, "health_bridge", True)
            self._restart_health_bridge()
            message = "Apple Health Bridge enabled. I am listening on the private network."
            self._append_chat("System", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:disable|stop|turn off|deactivate)\s+(?:apple\s+)?health\s+bridge\b", lowered):
            set_integration_enabled(self.assistant.settings, "health_bridge", False)
            if self.health_bridge is not None:
                self.health_bridge.stop()
                self.health_bridge = None
            self.health_var.set("Disabled")
            message = "Apple Health Bridge disabled. No health updates will be accepted."
            self._append_chat("System", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        activity_match = re.search(r"\b(?:i am|i'm|im)\s+(exercising|working out|running|walking|resting|sleeping|studying|coding|gaming|driving|outside|stressed|relaxing|doing homework|writing)\b", lowered)
        if activity_match:
            self._set_health_activity(activity_match.group(1), source)
            return True
        if any(phrase in lowered for phrase in ["stop talking", "stop speaking", "be quiet", "quiet please", "cancel speech"]):
            self.stop_speaking()
            if source == "overlay":
                self._set_overlay_response("JARVIS: Speech stopped.")
            return True
        wake_on = any(phrase in lowered for phrase in ["wake word", "wake listening", "always listening", "wake mode"])
        if wake_on and any(verb in lowered for verb in ["enable", "start", "turn on", "activate"]):
            self.wake_enabled_var.set(True)
            self.start_wake_listener()
            message = f"Wake listening enabled. Say {str(self.assistant.settings.get('wake_phrase', 'Jarvis')).title()} followed by a command."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if wake_on and any(verb in lowered for verb in ["disable", "stop", "turn off", "deactivate"]):
            self.stop_wake_listener()
            self._append_chat("JARVIS", "Wake listening disabled.")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Wake listening disabled.")
            return True
        if re.search(r"\b(?:run|stay|keep running|go)\s+(?:in\s+)?(?:the\s+)?background\b", lowered) or re.search(
            r"\b(?:hide|close|minimize)\s+(?:yourself|jarvis|the\s+window)(?:\s+to\s+background)?\b",
            lowered,
        ):
            self.run_in_background(source)
            return True
        if re.search(r"\b(?:turn|shut|power)\s+(?:yourself\s+)?off\b", lowered) or re.search(
            r"\b(?:quit|exit|close|stop)\s+(?:all\s+)?(?:jarvis|instances|jarvis\s+instances)\b",
            lowered,
        ):
            self.turn_off_all_instances(source)
            return True
        if re.search(r"\b(?:show|restore|open|bring back)\s+(?:yourself|jarvis|main window|command center)\b", lowered):
            self.show_main_window()
            if source == "overlay":
                self._set_overlay_response("JARVIS: Command Center restored.")
            return True
        browser_search = re.search(r"\b(?:search|look up)\s+(?:the\s+)?(?:web|internet|jarvis engine)\s+(?:for\s+)?(.+)", text, re.IGNORECASE)
        if browser_search:
            query = browser_search.group(1).strip()
            self.open_browser_panel()
            self.browser_address_var.set(query)
            self.after(500, self._browser_go)
            message = f"Searching JARVIS Engine for {query}."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:open|show|launch|bring up|start)\s+(?:the\s+)?(?:browser|jarvis engine|web browser)\b", lowered):
            self.open_browser_panel()
            message = "JARVIS Engine online. Try not to open forty-seven tabs immediately."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:open|show|launch|bring up|start)\s+(?:the\s+)?(?:video news|news videos|video headlines|video news panel)\b", lowered):
            self.open_video_news_panel()
            message = "Opening video news. Moving pictures, verified sources, and mercifully no autoplay."
            self._append_chat("JARVIS", message)
            self._set_command_status("Video news opened")
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:open|show|launch|bring up|start)\s+(?:the\s+)?(?:news|headlines|news feed|news panel)\b", lowered) or re.search(r"\bwhat(?:'s| is)\s+(?:in\s+)?(?:the\s+)?news\b", lowered):
            self.open_news_panel()
            message = "Opening the news feed. I will try to keep the existential dread neatly formatted."
            self._append_chat("JARVIS", message)
            self._set_command_status("News feed opened")
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:start|enable|turn on|activate)\s+(?:the\s+)?(?:webcam|camera|hand)?\s*gestures?\b", lowered):
            self.start_webcam_gestures()
            message = "Webcam gesture control is starting. Wave when you are ready."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(?:stop|disable|turn off|deactivate)\s+(?:the\s+)?(?:webcam|camera|hand)?\s*gestures?\b", lowered):
            self.stop_webcam_gestures()
            message = "Webcam gesture control disabled."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        gesture_mode_match = re.search(r"\b(?:set|switch|change)\s+(?:webcam|camera|hand|gesture)?\s*(?:control\s+)?(?:to\s+)?(safe|armed|disabled)(?:\s+mode)?\b", lowered)
        if gesture_mode_match:
            mode = gesture_mode_match.group(1).title()
            self._set_webcam_gesture_mode(mode)
            message = f"Webcam gesture mode set to {mode}."
            self._append_chat("JARVIS", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return True
        if re.search(r"\b(open|show|launch)\s+(?:webcam\s+|camera\s+|hand\s+)?(gesture|gestures|gesture control|hand control)\b", lowered):
            self.open_gesture_pad_window()
            self._append_chat("System", "Webcam Gesture Control opened.")
            self._set_command_status("Webcam Gesture Control opened")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Webcam Gesture Control opened.")
            return True
        if re.search(r"\b(?:run|start|perform)\s+(?:code|project|coding)?\s*diagnostics\b", lowered) or re.search(r"\bdiagnose\s+(?:my\s+)?(?:code|project|workspace)\b", lowered):
            self._set_command_center_panel_visible("code", True)
            self._run_coding_diagnostics()
            return True
        if re.search(r"\b(?:run|start)\s+(?:the\s+)?(?:selected\s+)?(?:code\s+check|project\s+tests?|tests?|approved\s+runner)\b", lowered):
            self._set_command_center_panel_visible("code", True)
            self._run_selected_code_runner()
            return True
        if re.search(r"\b(?:show|preview|restore)\s+(?:the\s+)?latest\s+(?:code\s+)?backup\b", lowered):
            self._set_command_center_panel_visible("code", True)
            self._preview_latest_code_backup()
            return True
        if re.search(r"\b(?:discard|cancel)\s+(?:the\s+)?(?:pending\s+|proposed\s+)?code\s+edit\b", lowered):
            self._discard_pending_code_edit()
            return True
        if re.search(r"\b(?:apply|accept)\s+(?:the\s+)?(?:pending\s+|proposed\s+)?code\s+edit\b", lowered):
            self._apply_pending_code_edit()
            return True
        if re.search(r"\b(open|show|launch)\s+(?:the\s+)?(?:coding|code)\s+(?:workspace|helper|panel)\b", lowered) or lowered in {"code helper", "coding workspace"}:
            self._set_command_center_panel_visible("code", True)
            self._append_chat("System", "Coding Workspace opened in the Command Center.")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Coding Workspace opened.")
            return True
        if re.search(r"\b(?:close|hide|collapse)\s+(?:the\s+)?(?:coding|code)\s+(?:workspace|helper|panel)\b", lowered):
            self._set_command_center_panel_visible("code", False)
            return True
        if re.search(r"\b(open|show|launch)\s+(layout|layouts|workspace layouts|workspace manager)\b", lowered):
            self.open_workspace_layout_window()
            self._append_chat("System", "Workspace Layouts opened.")
            self._set_command_status("Workspace Layouts opened")
            if source == "overlay":
                self._set_overlay_response("JARVIS: Workspace Layouts opened.")
            return True
        if re.search(r"\b(?:read|review|critique)\s+(?:my\s+)?(?:google\s+doc|doc|document|novel|chapter|draft|manuscript)\b", lowered) or re.search(
            r"\b(?:read it out loud|read this out loud|give feedback on my writing|writing feedback)\b",
            lowered,
        ):
            self._start_document_read_and_review(source)
            return True
        layout_match = re.search(r"\b(?:apply|use|switch to)\s+(full command center|focus overlay|diagnostics wall|minimal console)\b", lowered)
        if layout_match:
            wanted = layout_match.group(1)
            for layout in self._workspace_layouts():
                if str(layout.get("name", "")).lower() == wanted:
                    self._apply_workspace_layout(layout)
                    if source == "overlay":
                        self._set_overlay_response(f"JARVIS: Applied {layout.get('name')}.")
                    return True
            self._append_chat("System", f"I could not find the layout {wanted}.")
            return True
        return False

    def _start_document_read_and_review(self, source: str = "main") -> None:
        if self.document_review_running:
            message = "A document review is already running. One manuscript at a time; civilization depends on it."
            self._append_chat("System", message)
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: {message}")
            return
        self.document_review_running = True
        self._set_status("Reading Document...")
        self._set_command_status("Preparing document read-through...")
        self._append_chat("System", "Document read-through started. I will try to focus your writing window, copy the text, read it aloud, then give feedback.")
        if source == "overlay":
            self._set_overlay_response("JARVIS: Starting document read-through and critique.")
        threading.Thread(target=self._document_read_and_review_worker, daemon=True).start()

    def _document_read_and_review_worker(self) -> None:
        try:
            title = self._focus_likely_writing_window()
            if not title:
                message = "I could not find a likely Google Docs, Word, novel, chapter, draft, or manuscript window. Open the document, then ask again."
                self._append_chat("System", message)
                self._set_overlay_response(f"JARVIS: {message}")
                return
            self._set_command_status(f"Capturing document: {title[:70]}")
            time.sleep(0.5)
            ok, document_text, capture_message = capture_active_document_text()
            if not ok:
                message = f"{capture_message} Click inside the document body once, then ask me again."
                self._append_chat("System", message)
                self._set_overlay_response(f"JARVIS: {message}")
                self.assistant.record_action("document_read_review", {"window": title}, "medium", False, message, verified=True)
                return

            word_count = len(document_text.split())
            chunk_size = int(self.assistant.settings.get("document_read_chunk_chars", 850))
            chunks = chunk_text_for_tts(document_text, max(250, min(1200, chunk_size)))
            if not chunks:
                message = "I captured the document, but there was no readable text to speak."
                self._append_chat("System", message)
                return

            self._append_chat("System", f"{capture_message} Reading {word_count} words in {len(chunks)} speech chunks.")
            self._set_overlay_response(f"JARVIS: Reading {word_count} words. Feedback follows after the final line.")
            self._set_command_status(f"Reading document aloud: {word_count} words")
            self.speak(f"I captured {word_count} words. Beginning read-through now.")
            for index, chunk in enumerate(chunks, start=1):
                self._set_command_status(f"Reading document chunk {index}/{len(chunks)}")
                self.speak(chunk)
            self.tts_queue.join()

            self._set_status("Thinking...")
            self._set_command_status("Generating honest writing feedback...")
            feedback = self.assistant.review_document_text(document_text, source_title=title)
            self._append_chat("JARVIS", feedback)
            self._set_overlay_response(f"JARVIS: {feedback[:900] + ('...' if len(feedback) > 900 else '')}")
            self.speak("Read-through complete. Here is the honest feedback.")
            self.speak(feedback)
            self.assistant.record_action(
                "document_read_review",
                {"window": title, "words": word_count},
                "medium",
                True,
                f"Read {word_count} words and generated feedback.",
                verified=True,
            )
        except Exception as exc:
            message = f"Document review failed: {exc}"
            self._append_chat("System", message)
            self._set_overlay_response(f"JARVIS: {message}")
            self.assistant.record_action("document_read_review", {}, "medium", False, message, verified=True)
        finally:
            self.document_review_running = False
            self._set_status("Online")
            self._set_command_status("Document review complete")

    def _focus_likely_writing_window(self) -> str:
        current = get_active_window_title()
        if self._looks_like_writing_window(current.lower()):
            return current
        for query in ["google docs", "docs", "microsoft word", "word", "novel", "chapter", "draft", "manuscript"]:
            title = focus_window_by_title(query)
            if title and self._looks_like_writing_window(title.lower()):
                time.sleep(0.6)
                return get_active_window_title()
        return ""

    def interrupt_and_listen(self) -> None:
        self.stop_speaking(silent=True)
        self.listen_once()

    def listen_once(self) -> None:
        if self.is_listening:
            self._append_chat("System", "Voice capture is already running.")
            self._set_command_status("Voice capture already running")
            return
        if self.voice_backend == "unavailable":
            self._append_chat("System", "Microphone is unavailable. Text input remains perfectly civilized.")
            return
        self.stop_speaking(silent=True)
        self._wake_pause.set()
        self._append_chat("System", "Voice capture started. Speak now.")
        self._set_command_status("Voice capture starting...")
        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self) -> None:
        self.is_listening = True
        if self.wake_enabled_var.get():
            time.sleep(0.3)
        self._set_status("Listening...")
        self._set_mic_status("Listening")
        self._voice_audio_fallback = None
        try:
            if self.voice_backend == "pyaudio" and self.microphone is not None:
                with self.microphone as source:
                    self._set_command_status("Calibrating microphone...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    self._set_command_status("Listening... speak now")
                    audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=12)
            else:
                audio = self._record_with_sounddevice()
            self._set_status("Processing voice...")
            self._set_mic_status("Processing")
            self._set_command_status("Transcribing voice...")
            self._append_chat("System", "Voice captured. Transcribing now.")
            text = self._transcribe_voice(audio)
            self._append_chat("System", f"Heard: {text}")
            wake = self.assistant.settings.get("wake_phrase", "jarvis").lower()
            if wake not in text.lower() and not text.strip():
                self._append_chat("System", "I heard something, but not enough to dignify with analysis.")
                return
            self._append_chat("You", text)
            self._set_command_status(f"Working on: {text[:80]}")
            self._process_command(text)
        except sr.WaitTimeoutError:
            self._append_chat("System", "No voice detected. I waited with admirable patience.")
        except sr.UnknownValueError:
            self._append_chat(
                "System",
                "I couldn't understand that. The mic has signal now, so try the non-AirPods microphone if this keeps happening; Bluetooth headset audio can be tragically crunchy.",
            )
        except Exception as exc:
            self._append_chat("System", f"Voice input failed: {exc}")
        finally:
            self.is_listening = False
            self._wake_pause.clear()
            mic_state = f"Wake ready: {str(self.assistant.settings.get('wake_phrase', 'jarvis')).title()}" if self.wake_enabled_var.get() else ("Ready" if self.voice_backend != "unavailable" else "Unavailable")
            self._set_mic_status(mic_state)
            self._set_status("Online")
            self._set_command_status("Idle")

    def _transcribe_voice(self, audio: sr.AudioData) -> str:
        provider = str(self.assistant.settings.get("voice_transcription_provider", "auto")).lower()
        google_error: Exception | None = None
        candidates = [audio]
        if self._voice_audio_fallback is not None and self._voice_audio_fallback is not audio:
            candidates.append(self._voice_audio_fallback)

        if provider in {"auto", "google"}:
            for index, candidate in enumerate(candidates):
                try:
                    label = "enhanced audio" if index else "audio"
                    self._set_command_status(f"Transcribing {label} with Google...")
                    return self.recognizer.recognize_google(candidate)
                except sr.UnknownValueError as exc:
                    google_error = exc
                    continue
                except Exception as exc:
                    google_error = exc
                    break
            if provider == "google" and google_error is not None:
                raise google_error
            self._append_chat("System", "Google could not transcribe it; trying Gemini transcription.")

        if provider in {"auto", "gemini"}:
            gemini_error: Exception | None = None
            for index, candidate in enumerate(candidates):
                try:
                    label = "enhanced audio" if index else "audio"
                    self._set_command_status(f"Transcribing {label} with Gemini...")
                    text = self.assistant.transcribe_audio_with_gemini(candidate)
                    if text:
                        return text
                except Exception as exc:
                    gemini_error = exc
            if provider == "gemini" and gemini_error is not None:
                raise gemini_error
            if gemini_error is not None:
                self._append_chat("System", f"Gemini transcription also failed: {gemini_error}")

        if isinstance(google_error, sr.UnknownValueError):
            raise google_error
        raise sr.UnknownValueError()

    def _record_with_sounddevice(self) -> sr.AudioData:
        if sd is None:
            raise RuntimeError("sounddevice is not installed")
        if np is None:
            raise RuntimeError("NumPy is not installed, and sounddevice needs it for voice recording")

        configured_index = self.assistant.settings.get("voice_input_device_index")
        device_index = configured_index if isinstance(configured_index, int) else None
        try:
            device_info = sd.query_devices(device_index, kind="input") if device_index is not None else sd.query_devices(kind="input")
        except Exception:
            self._append_chat("System", f"Saved microphone {device_index} is unavailable. Falling back to the default input.")
            self.assistant.settings["voice_input_device_index"] = None
            save_settings(self.assistant.settings)
            device_index = None
            device_info = sd.query_devices(kind="input")
        sample_rate = int(float(device_info.get("default_samplerate", 44100)))
        device_name = str(device_info.get("name", "Unknown microphone"))
        duration_seconds = int(self.assistant.settings.get("voice_record_seconds", 10))
        duration_seconds = max(4, min(15, duration_seconds))
        device_label = f"{device_index}: {device_name}" if device_index is not None else f"default: {device_name}"
        endpointing = bool(self.assistant.settings.get("voice_endpointing_enabled", True))
        self._append_chat("System", f"Listening for up to {duration_seconds} seconds using {device_label}.")
        self._set_status("Recording...")

        audio_queue: queue.Queue[np.ndarray] = queue.Queue()

        def callback(indata: np.ndarray, _frames: int, _time_info: Any, status: Any) -> None:
            if status:
                return
            audio_queue.put(indata.copy())

        chunks: list[np.ndarray] = []
        noise_peaks: list[int] = []
        speech_started = False
        last_voice_at = 0.0
        started = time.monotonic()
        last_update = 0.0
        silence_seconds = max(0.6, min(2.5, float(self.assistant.settings.get("voice_silence_seconds", 1.0))))
        minimum_seconds = max(0.3, min(3.0, float(self.assistant.settings.get("voice_minimum_seconds", 0.7))))
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            device=device_index,
            callback=callback,
        ):
            while time.monotonic() - started < duration_seconds:
                try:
                    chunk = audio_queue.get(timeout=0.25)
                    chunks.append(chunk)
                    chunk_peak = int(np.max(np.abs(chunk))) if chunk.size else 0
                    elapsed = time.monotonic() - started
                    if elapsed < 0.45 and not speech_started:
                        noise_peaks.append(chunk_peak)
                    baseline = int(np.median(noise_peaks)) if noise_peaks else 100
                    threshold = max(260, min(5000, baseline * 3 + 160))
                    if chunk_peak >= threshold:
                        speech_started = True
                        last_voice_at = time.monotonic()
                    elif endpointing and speech_started and elapsed >= minimum_seconds and time.monotonic() - last_voice_at >= silence_seconds:
                        self._set_command_status("Speech complete. Transcribing...")
                        break
                except queue.Empty:
                    pass
                now = time.monotonic()
                if now - last_update >= 0.4:
                    recent = np.concatenate(chunks[-8:]).reshape(-1) if chunks else np.array([], dtype=np.int16)
                    live_peak = int(np.max(np.abs(recent))) if recent.size else 0
                    remaining = max(0, int(round(duration_seconds - (now - started))))
                    state = "Listening" if not speech_started else "Hearing you"
                    self._set_mic_status(f"{state} | peak {live_peak}")
                    self._set_command_status(f"{state}... {remaining}s maximum")
                    last_update = now

        if chunks:
            audio_array = np.concatenate(chunks).astype(np.int16).reshape(-1)
        else:
            audio_array = np.array([], dtype=np.int16)
        peak = int(np.max(np.abs(audio_array))) if audio_array.size else 0
        self._append_chat("System", f"Mic level peak: {peak}/32767.")

        if peak < 250:
            self._append_chat("System", "The microphone signal is extremely quiet. Windows may be using the wrong mic.")
        elif peak < 1800:
            gain = min(12.0, 9000.0 / max(peak, 1))
            boosted = np.clip(audio_array.astype(np.float32) * gain, -32768, 32767).astype(np.int16)
            audio_array = boosted
            self._append_chat("System", f"Boosted quiet microphone audio by {gain:.1f}x before transcription.")

        primary_audio = audio_array.copy()
        cleaned_audio, cleanup = clean_voice_audio(audio_array, sample_rate)
        self._append_chat(
            "System",
            f"Cleaned audio peak: {cleanup['clean_peak']}/32767, RMS: {cleanup['clean_rms']}.",
        )
        self._voice_audio_fallback = sr.AudioData(cleaned_audio.tobytes(), sample_rate, 2)
        return sr.AudioData(primary_audio.tobytes(), sample_rate, 2)

    def _process_command(self, text: str, source: str = "main") -> None:
        self._set_status("Acting...")
        self._set_command_status(f"Acting: {text[:80]}")
        ledger_count_before = len(self.assistant.action_ledger)
        try:
            role, response = self.assistant.handle_command(text)
            speaker = "JARVIS" if role in {"assistant", "action"} else "System"
            if role == "action":
                if len(self.assistant.action_ledger) == ledger_count_before and not re.search(r"\b(action history|action ledger|recent actions|what did you do)\b", text, re.I):
                    success = self.assistant.action_message_indicates_success(response)
                    self.assistant.record_action(text[:80], {}, self.assistant.last_risk or "safe", success, response, verified=success)
                else:
                    self.assistant.last_action = text[:80]
                    if self.assistant.last_risk not in {"medium", "high"}:
                        self.assistant.last_risk = "safe"
            self._append_chat(speaker, response)
            if source == "overlay":
                preview = response.strip()
                if len(preview) > 900:
                    preview = preview[:897] + "..."
                self._set_overlay_response(f"JARVIS: {preview}")
            if self.voice_enabled_var.get() and role != "error":
                self.speak(response)
        except Exception as exc:
            if source == "overlay":
                self._set_overlay_response(f"JARVIS: I hit an error: {exc}")
            raise
        finally:
            self._set_status("Online")
            self._set_command_status("Task complete")

    def stop_speaking(self, silent: bool = False) -> None:
        was_speaking = self._tts_speaking.is_set() or not self.tts_queue.empty()
        self._tts_stop.set()
        while True:
            try:
                self.tts_queue.get_nowait()
                self.tts_queue.task_done()
            except queue.Empty:
                break
        with self._tts_process_lock:
            process = self._tts_process
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass
        engine = self._tts_engine
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass
        if was_speaking and not silent:
            self._append_chat("System", "Speech interrupted.")
        if was_speaking:
            self._set_status("Listening..." if self.is_listening else "Online")
            self._set_command_status("Speech interrupted")

    def speak(self, text: str) -> None:
        clean_text = self._clean_tts_text(text)
        if clean_text:
            self._tts_stop.clear()
            now = time.monotonic()
            if clean_text == self._last_spoken_text and now - self._last_spoken_at < 20:
                return
            self._last_spoken_text = clean_text
            self._last_spoken_at = now
            max_chars = int(self.assistant.settings.get("tts_max_chars", 650))
            for chunk in chunk_text_for_tts(clean_text, max_chars=max(250, min(900, max_chars))):
                self.tts_queue.put(chunk)

    def _clean_tts_text(self, text: str) -> str:
        text = re.sub(r"\[System note:.*?\]", "", text, flags=re.I | re.S)
        text = re.sub(r"https?://\S+", "link", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4000]

    def _tts_worker(self) -> None:
        while True:
            text = self.tts_queue.get()
            if self._tts_stop.is_set():
                self.tts_queue.task_done()
                continue
            self._tts_speaking.set()
            self._set_status("Speaking...")
            try:
                use_sapi = (
                    self.tts_backend == "windows_sapi"
                    and platform.system().lower() == "windows"
                    and time.monotonic() >= self._tts_cooldown_until
                )
                if use_sapi:
                    self._speak_with_windows_sapi(text)
                else:
                    self._speak_with_pyttsx3(text)
                self._tts_failures = 0
            except Exception as exc:
                if self._tts_stop.is_set():
                    continue
                self._tts_failures += 1
                try:
                    self._speak_with_pyttsx3(text)
                    self._tts_failures = 0
                except Exception as fallback_exc:
                    if not self._tts_stop.is_set():
                        self._report_tts_error(exc, fallback_exc)
                    if self._tts_failures >= 2:
                        cooldown = int(self.assistant.settings.get("tts_error_cooldown_seconds", 45))
                        self._tts_cooldown_until = time.monotonic() + max(10, cooldown)
            finally:
                self._tts_speaking.clear()
                self._set_status("Online")
                self.tts_queue.task_done()

    def _report_tts_error(self, exc: Exception, fallback_exc: Exception | None = None) -> None:
        now = time.monotonic()
        cooldown = int(self.assistant.settings.get("tts_error_cooldown_seconds", 45))
        if now - self._last_tts_error_at < max(10, cooldown):
            return
        self._last_tts_error_at = now
        primary = self._short_error_text(exc)
        if fallback_exc is not None:
            message = f"Voice engine hiccup: {primary}; fallback also failed: {self._short_error_text(fallback_exc)}"
        else:
            message = f"Voice engine hiccup: {primary}"
        self._append_chat("System", message)
        self._set_command_status("Voice engine recovered or skipped a speech chunk")

    def _short_error_text(self, exc: Exception) -> str:
        text = re.sub(r"\s+", " ", str(exc)).strip()
        text = re.sub(r"At line:\d+.*", "", text, flags=re.I)
        text = re.sub(r"\+ CategoryInfo:.*", "", text, flags=re.I)
        return (text[:180] + "...") if len(text) > 180 else (text or exc.__class__.__name__)

    def _speak_with_windows_sapi(self, text: str) -> None:
        preferred_terms = "|".join(re.escape(term) for term in self._preferred_voice_terms())
        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.Rate = {self._sapi_rate()}; "
            f"$preferred = '{preferred_terms}'; "
            "$voice = $synth.GetInstalledVoices() | "
            "Where-Object { $_.Enabled -and ("
            "$_.VoiceInfo.Name -match $preferred -or "
            "$_.VoiceInfo.Culture.Name -match $preferred -or "
            "$_.VoiceInfo.Culture.DisplayName -match $preferred"
            ") } | "
            "Sort-Object @{Expression={ if ($_.VoiceInfo.Gender -eq 'Male') { 0 } else { 1 } }}, "
            "@{Expression={ if ($_.VoiceInfo.Culture.Name -eq 'en-GB') { 0 } else { 1 } }} | "
            "Select-Object -First 1; "
            "if ($voice) { $synth.SelectVoice($voice.VoiceInfo.Name) }; "
            "$synth.Speak($env:JARVIS_TTS_TEXT); "
            "$synth.Dispose()"
        )
        env = os.environ.copy()
        env["JARVIS_TTS_TEXT"] = text
        startupinfo = None
        creationflags = 0
        timeout_seconds = max(20, min(90, 18 + len(text) // 18))
        if platform.system().lower() == "windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            env=env,
            startupinfo=startupinfo,
            creationflags=creationflags,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with self._tts_process_lock:
            self._tts_process = process
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            raise RuntimeError(f"Windows SAPI timed out after {timeout_seconds}s") from exc
        finally:
            with self._tts_process_lock:
                if self._tts_process is process:
                    self._tts_process = None
        if self._tts_stop.is_set():
            return
        if process.returncode != 0:
            error_text = (stderr or stdout or "Unknown SAPI failure").strip()
            error_text = re.sub(r"\s+", " ", error_text)
            raise RuntimeError(error_text[:220])

    def _sapi_rate(self) -> int:
        return max(-10, min(10, round((self.tts_rate - 175) / 20)))

    def _speak_with_pyttsx3(self, text: str) -> None:
        pythoncom = None
        try:
            try:
                import pythoncom as pythoncom_module

                pythoncom = pythoncom_module
                pythoncom.CoInitialize()
            except Exception:
                pythoncom = None
            engine = pyttsx3.init()
            self._tts_engine = engine
            engine.setProperty("rate", self.tts_rate)
            if self.tts_voice_id:
                engine.setProperty("voice", self.tts_voice_id)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        finally:
            self._tts_engine = None
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _append_chat(self, sender: str, message: str) -> None:
        def write() -> None:
            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", f"{sender}: {message}\n\n")
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")

        self.after(0, write)

    def _set_status(self, status: str) -> None:
        self.after(0, lambda: self.status_var.set(status))

    def _set_command_status(self, status: str) -> None:
        self.after(0, lambda: self.command_var.set(status))

    def _set_mic_status(self, status: str) -> None:
        self.after(0, lambda: self.mic_var.set(status))

    def _on_close(self) -> None:
        self._save_ui_layout_now()
        self._monitor_stop.set()
        self._project_watcher_stop.set()
        self._wake_stop.set()
        if self.health_bridge is not None:
            self.health_bridge.stop()
            self.health_bridge = None
        if self.phone_bridge is not None:
            self.phone_bridge.stop()
            self.phone_bridge = None
        self._stop_browser_engine()
        self.stop_speaking(silent=True)
        self._gesture_stop.set()
        if self._gesture_capture is not None:
            try:
                self._gesture_capture.release()
            except Exception:
                pass
        self.destroy()


def run_packaged_hand_tracking_self_test() -> bool:
    if mp is None or np is None or not hasattr(mp, "tasks") or not HAND_LANDMARKER_MODEL_PATH.exists():
        return False
    landmarker = None
    try:
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_LANDMARKER_MODEL_PATH)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
        )
        landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        blank = np.zeros((64, 64, 3), dtype=np.uint8)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=blank)
        landmarker.detect_for_video(image, 1)
        return True
    except Exception:
        return False
    finally:
        if landmarker is not None:
            landmarker.close()


if __name__ == "__main__":
    if "--self-test-hand-tracking" in sys.argv:
        raise SystemExit(0 if run_packaged_hand_tracking_self_test() else 1)
    app = JarvisApp()
    app.mainloop()
