# JARVIS Desktop Assistant

A beginner-friendly Windows desktop AI assistant inspired by the polished, futuristic feeling of JARVIS-style assistants. It supports text commands, voice input, speech output, active-window awareness, safe local actions, and Gemini or OpenAI-backed chat.

## Setup

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

Voice input uses `sounddevice` by default. The main app can run without it, but the microphone button will be unavailable. To add microphone support, run:

```powershell
pip install -r requirements-voice.txt
```

When using the `sounddevice` backend, the **Voice** button listens for up to 10 seconds but normally stops about one second after you finish speaking. Pressing **Voice** or Ctrl + Space while JARVIS is talking interrupts speech immediately and starts a new voice turn.

The **Wake** switch is opt-in. When enabled, JARVIS monitors local microphone levels for speech and transcribes detected utterances to check for the configured `wake_phrase` (normally `Jarvis`). Say `Jarvis, open Chrome`, or say `Jarvis` and wait for `Yes?` before giving a follow-up command. Because wake-word matching happens after transcription, detected speech may be sent to the configured Google/Gemini transcription provider while Wake mode is enabled.

If the mic level is near zero, click **Mic** and choose another input device. You can also type `list microphones` and then `use microphone 15` with the device number you want.

If Bluetooth earbuds such as AirPods show a strong peak but still fail transcription, leave `voice_transcription_provider` set to `auto` in `settings.json`. JARVIS tries Google speech recognition first, then falls back to Gemini audio transcription when Google cannot understand the headset audio.

PyAudio is optional. If you specifically want PyAudio and it fails on Windows, Python 3.11 or 3.12 is usually easier than very new Python versions. You can also try:

```powershell
pip install pipwin
pipwin install pyaudio
```

4. Create a `.env` file:

```powershell
Copy-Item config.example.env .env
```

5. For local development, edit `.env` and add your Gemini API key:

```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
```

Public release builds do not contain this key. They use the secure Cloudflare
Worker URL stored in `distribution_config.json`; the secret remains on the
server. See `cloudflare-worker/README.md` for deployment.

The `.env` file should be here:

```text
C:\Path\To\JARVIS\.env
```

6. Run the app:

```powershell
python jarvis.py
```

Or double-click:

```text
Launch JARVIS.bat
```

## Making It Feel Like An App

The easiest launcher is [Launch JARVIS.bat](Launch%20JARVIS.bat). Double-click it from the project folder and it will start JARVIS without typing `python jarvis.py`.

To build a Windows `.exe`, install the build dependency:

```powershell
pip install -r requirements-build.txt
```

Then run:

```powershell
.\build_exe.bat
```

If the build succeeds, the executable will be here:

```text
dist\JARVIS Desktop Assistant\JARVIS Desktop Assistant.exe
```

For desktop shortcuts, point the shortcut at `Launch JARVIS.vbs` in the project root instead of the exe inside `dist`. Rebuilds delete and recreate the `dist` folder, which can break shortcuts or pinned taskbar items. The launcher file stays in place and opens the latest rebuilt exe.

## Controls

- Type a command in the bottom input box and press Enter or Send.
- Press **Voice** to interrupt any current reply and speak immediately.
- If the `keyboard` package can register global hotkeys, Ctrl + Space interrupts speech and starts voice input.
- Toggle **Wake** for optional wake-phrase listening; it remains off until you enable it.
- Click **Overlay** or press Ctrl + Alt + J to summon a small always-on-top command bar while using other windows.
- Click **Watcher** to add project folders JARVIS should monitor for errors.
- Click **Code** in the top bar or type `open coding workspace` to browse, search, preview, and ask Gemini about source files in a selected project.
- Click **Music** to tune preferred music app, Apple Music automation, vision-assisted play clicks, and fallbacks.
- Click **Music -> Phone Bridge** or type `phone bridge setup` to let an iPhone Shortcut fetch approved mobile actions, such as playing Apple Music on your phone.
- Click **Integrations** to enable free integrations, check setup status, and open setup docs.
- Click **Integrations** then **Apple Health Bridge**, or type `health setup`, to pair an iPhone Shortcut for Apple Watch wellness context.
- Click **Panels** or the Core/Chat/Side buttons in the Command Center header to collapse sections, restore them, or reset the draggable in-window layout.
- Click **Missions** to run or save multi-step JARVIS workflows.
- Click **Hands** to open webcam gesture control. The camera starts only after you press **Start**.
- Click **Layouts** to switch between saved command-center workspace layouts.
- Toggle Speak to enable or disable text-to-speech responses.
- Say or type `run in the background` to hide the main window while keeping JARVIS running. Ctrl + Alt + J can bring up the overlay, and the overlay has a **Main** button to restore the Command Center.
- Say or type `turn off`, `shut yourself off`, or `close all JARVIS instances` to shut down JARVIS.

## Command Center Layout

The main UI uses a Command Center layout with a central animated core, telemetry cards, a chat feed, and a controls/status panel. The `Core`, `Chat`, and `Status` panels have small drag handles, so you can click and drag them around inside the same JARVIS window. Each panel also has a bottom-right resize grip for mouse scaling. Panel positions and sizes are saved in `settings.json`, and the **Panels** manager can reset the layout or restore hidden sections.

## Coding Workspace

Open the code helper with the **Code** button, choose a project folder, and select a source file to preview it. The search box checks both relative file paths and sampled source contents while skipping dependency, cache, backup, build, and version-control folders.

Enter a question such as `What does this class do?` or `Where could this fail?` and press **Explain**. JARVIS sends the selected file and question to Gemini, then places the explanation in the main chat. The selected workspace is saved, but source contents and code questions are not stored as chat history.

Phase 2 adds controlled edits:

1. Select a UTF-8 source file under 50,000 characters.
2. Describe the change in the question box.
3. Press **Propose Edit**.
4. Review the unified diff in the preview.
5. Choose **Apply** or **Discard**.

Apply follows the selected JARVIS permission mode. Ask for approval and Safe Mode show a confirmation before writing. Every successful edit creates a timestamped copy under `.jarvis_backups` inside the selected project. JARVIS also rejects a proposal if the source file changed after the diff was created.

Use **Latest Backup** to preview restoration of the newest backup as another diff. Applying the restoration first backs up the current file, so recovery is reversible too.

**Diagnostics** performs local Python, JSON, and TOML syntax checks, detects unresolved merge markers, identifies the project type, and summarizes source-file types. These checks do not depend on Gemini.

The **Approved runner** menu only shows fixed runners discovered from the project, such as Python `unittest`, Python compile checks, pytest when installed, Node tests, Godot headless checks, or language-native test tools. JARVIS never accepts a generated terminal command or generated arguments. Test runners:

- use `shell=False`;
- receive a sanitized environment without secret-like environment variables;
- have a two-minute timeout;
- terminate their child processes on timeout;
- require confirmation according to the selected permission mode and always in Safe Mode.

Project tests can still read files located inside their own workspace, so only run projects you trust.

The agent tool registry can now inspect the selected coding workspace, search source files, read approved source files, run diagnostics, and select an approved runner. `.env`, private-key, credential, and similar files are blocked from AI context, while secret-like assignments in readable source are redacted.

Voice or text examples:

```text
open coding workspace
diagnose my project
search my project for ToolRegistry
run the selected code check
show the latest code backup
apply the proposed code edit
discard the code edit
```

The workspace still cannot run arbitrary terminal commands.
## Mission Dashboard

The **Missions** dashboard runs saved multi-step workflows through the same safe command router as normal chat commands. Risky steps still pause for confirmation, and every mission writes a final summary into the chat.

Default missions include:

- Coding Session
- Game Dev Session
- School Focus
- Laptop Diagnostics
- Command Center Check

You can add a custom mission by entering a name and semicolon-separated commands, such as:

```text
focus mode; open chrome; play music, you pick; start a focus timer for 25 minutes
```

## Webcam Hand Gestures And Layouts

The **Hands** panel uses the bundled MediaPipe Hand Landmarker model to track 21 three-dimensional hand landmarks locally.

- Wave repeatedly with a clearly open palm: JARVIS says hello after strict motion validation.
- Hold a stable index-point: move the cursor with landmark smoothing and a jitter dead zone.
- Pinch your thumb and index finger deliberately: click only when gesture control is **Armed**.
- **Safe** mode permits greetings and cursor movement but blocks clicks.
- **Disabled** mode ignores control gestures.

Generic OpenCV motion never controls or clicks the cursor. If landmark tracking is unavailable, the fallback is diagnostic-only. Webcam frames remain local and are not sent to Gemini.

Voice or text commands also work:

```text
start hand gestures
stop webcam gestures
set gesture control to safe
set gesture control to armed
open hand control
```

The **Layouts** window applies saved workspace arrangements:

- Full Command Center
- Focus Overlay
- Diagnostics Wall
- Minimal Console

You can also type commands like `open hand control`, `open layouts`, `apply focus overlay`, or `switch to minimal console`.


## Apple Health Bridge Without A Mac

JARVIS can receive Apple Watch health context without a Mac by using your iPhone as the bridge:

```text
Apple Watch / Apple Health -> iPhone Shortcut -> local Wi-Fi POST -> JARVIS on this PC
```

Open **Integrations** and choose **Apple Health Bridge**, or type:

```text
health setup
health status
I am exercising
I am coding
turn off health bridge
```

The setup panel shows a private local URL and pairing code. Keep your iPhone and PC on the same Wi-Fi. If Windows asks about firewall access, allow private networks.

Recommended iPhone Shortcut:

1. Open **Shortcuts** on your iPhone.
2. Tap **+** and name the shortcut `Send Health To JARVIS`.
3. Add **Find Health Samples**.
4. Set **Type** to **Heart Rate**.
5. Set sorting to **Start Date**, **Latest First**, and turn on **Limit** with a limit of `1`.
6. Add **Get Details of Health Samples**.
7. Set **Detail** to **Value**. This is the value you will use for `heart_rate`.
8. Add another **Get Details of Health Samples**.
9. Set **Detail** to **Start Date**. This is the value you will use for `timestamp`.
10. Add **Get Contents of URL**.
11. Put the Shortcut URL from JARVIS in the URL field.
12. Tap **Show More**.
13. Set **Method** to **POST**.
14. Set **Request Body** to **JSON**.
15. Add a header named `X-JARVIS-Health-Token` and paste the pairing code from JARVIS.
16. Under **Request Body -> JSON**, add two rows. For each row, choose **Text** as the field type.
17. Fill them in like this:
    - Left **Key** box: `heart_rate`; right **Text** box: the **Value** from step 7
    - Left **Key** box: `timestamp`; right **Text** box: the **Start Date** from step 9
18. Do not add `activity` or `source` unless you already know how to type literal text into Shortcuts. JARVIS will fill those in automatically.
19. Run the shortcut once and allow Health permissions when iOS asks.

If Shortcuts sends a value like `82 count/min` instead of plain `82`, JARVIS will extract the number.

Supported JSON keys are:

```json
{
  "token": "pairing-code-from-jarvis",
  "heart_rate": 82,
  "hrv": 41,
  "resting_heart_rate": 68,
  "timestamp": "2026-06-23T20:15:00",
  "activity": "coding",
  "source": "iPhone Shortcut"
}
```

Only `heart_rate` is required. `timestamp` is recommended. The other fields are optional.

Health readings are stored locally in a short rolling file and are used only for wellness context. JARVIS does not diagnose stress, illness, or emergencies. If a reading feels wrong or you feel unsafe, use real medical help instead of trusting the laptop with a glowing personality.

## JARVIS Phone Bridge

The Phone Bridge lets your iPhone fetch approved phone-side actions from JARVIS. The first supported action is Apple Music playback on your phone.

Open **Music -> Phone Bridge**, **Integrations -> JARVIS Phone Bridge**, or type:

```text
phone bridge setup
phone bridge status
play Master of Puppets on my phone
play Bad by Michael Jackson on Apple Music
```

When a song request is ambiguous, JARVIS can ask:

```text
Should I play this on this device, or on your mobile device, sir?
```

Recommended iPhone Shortcut:

1. Open **Shortcuts** on your iPhone.
2. Tap **+** and name it `JARVIS Phone Bridge`.
3. Add **Get Contents of URL**.
4. Put the Phone Bridge Shortcut URL from JARVIS in the URL field.
5. Tap **Show More**.
6. Add a header named `X-JARVIS-Phone-Token` and paste the pairing code from JARVIS.
7. Add **Get Dictionary Value**.
8. Set **Key** to `action`, and set **Dictionary** to **Contents of URL**.
9. Add **If**.
10. In the If action, tap the first blue value and choose the **Dictionary Value** from step 7.
11. Set the condition to **is**.
12. In the last field, type `play_apple_music` as plain text.
13. Drag the music actions below inside the If block, above **Otherwise**.
14. Inside the If block, add **Get Dictionary Value**.
15. Set **Key** to `query`, and set **Dictionary** to **Contents of URL**.
16. Add **Search Apple Music**. Search for the `query` value from step 15.
17. Add **Get Item from List** and choose **First Item**.
18. Add **Play Music** using that first item.

Run the Shortcut after JARVIS queues a mobile request. Keep your iPhone and PC on the same Wi-Fi. If Windows asks about firewall access, allow private networks.

## Example Commands

- `Open Chrome`
- `Open Visual Studio Code`
- `What window is open?`
- `Look at my screen`
- `What is on my screen?`
- `What should I click?`
- `Read my screen`
- `Play music, you pick`
- `Music status`
- `Can you open Apple Music and search my song?` then reply with the song name.
- `Open Apple Music and search for Bad by Michael Jackson`
- `Play Master of Puppets by Metallica`
- `Play Master of Puppets on my phone`
- `Phone bridge setup`
- `Search Google for Python decorators`
- `YouTube synthwave coding playlist`
- `Take a screenshot`
- `Volume up`
- `Mute volume`
- `Minimize this window`
- `Maximize this window`
- `Close this window` then `confirm`
- `Copy clipboard to hello from JARVIS`
- `Read clipboard`
- `Paste clipboard`
- `Type hello there`
- `Move mouse to 500 300`
- `Move my mouse`
- `Move my mouse to center`
- `Move my mouse left 200`
- `Where is my mouse?`
- `Click at 500 300`
- `Double click at 500 300`
- `Right click at 500 300`
- `Scroll down`
- `List windows`
- `Switch to Chrome`
- `Open downloads folder`
- `List downloads files`
- `Open newest file from downloads`
- `Create folder named Project Notes on desktop`
- `Open bluetooth settings`
- `System info`
- `Awareness status`
- `Health setup`
- `Health status`
- `I am exercising`
- `I am coding`
- `Turn off monitoring`
- `Turn on monitoring`
- `Watch C:\Users\YourName\Documents\MyProject`
- `Project watcher status`
- `Turn off project watcher`
- `Unwatch MyProject`
- `List tools`
- `coding mode`
- `safe mode`
- `normal mode`
- `mode status`
- `clear my recycle bin` then `confirm`
- `action history`
- `integration status`
- `list integrations`
- `Set my location to 123 Main Street, Chicago, IL`
- `Where am I?`
- `Directions to Target`
- `ETA to school`
- `Directions from Chicago, IL to Milwaukee, WI`
- `Pizza Hut near me`
- `Nearest gas station`
- `Turn on startup location`
- `Turn off startup location`
- `Agent open notepad and then type hello`
- `Use tools take a screenshot then analyze my screen`
- `Press enter`
- Use the floating Overlay bar to type commands while another app is open.
- `What time is it?`
- `Battery status`
- `Start a focus timer for 25 minutes`
- `Make a to-do list for finishing my game prototype`

## Laptop Access and Safety

JARVIS has a controlled set of local actions. He can open whitelisted apps, folders, websites, Windows Settings pages, control volume/media keys, manage the active window, smoothly move/click the mouse when you give explicit coordinates or directions, type/paste into the focused field, use the clipboard, take screenshots, create folders in known safe locations, list recent items in known folders, and report basic system status.

Location and directions are opt-in. Say `set my location to ...` to save a manual start point, or say `enable approximate IP location` if you want city-level lookup from your internet connection. Startup refresh can be enabled with `turn on startup location`; when enabled, JARVIS updates an approximate IP-based location when the app opens and reports the readable city/region/country instead of raw coordinates. Exact street-address reverse geocoding, nearby business lookup, fastest-route details, and exact ETA text require `GOOGLE_MAPS_API_KEY` in `.env` with the Geocoding API, Places API, Directions API, and Distance Matrix API enabled; otherwise Google Maps will show the live ETA in the browser.

Proactive monitoring watches laptop vitals in the background while the app is open. It updates the side panel with CPU, RAM, disk, battery, internet, and active-window focus time. It can alert you if CPU/RAM/disk get high, battery gets low, internet drops or returns, power state changes, or you spend a long session in one window. Use `awareness status`, `turn off monitoring`, or `turn on monitoring`.

Project Watcher monitors selected project folders for changed text/log/source files that contain error terms such as `traceback`, `exception`, `error:`, `failed`, `parser error`, `cannot infer`, and common import errors. It creates a baseline first, then alerts only when watched files change. Use the **Watcher** button or commands like `watch C:\path\to\project`, `project watcher status`, and `turn off project watcher`.

## Integrations

Click **Integrations** or type `integration status` to see which free integrations are enabled, ready, or missing setup. This panel does not store private tokens. API keys and tokens belong in `.env`; `settings.json` only stores harmless toggles and local URLs.

Built-in or ready-to-expand integrations include:

- Windows Control: local actions, clipboard, screenshots, volume, windows, folders, and safe app launching.
- Screen Vision: Gemini screenshot analysis.
- Mouse Control: safe cursor movement, clicks, scrolling, and typing confirmations.
- Gemini and optional OpenAI: AI provider support.
- Google Maps: location, readable addresses, nearby places, ETA, directions, and route details.
- Browser: Google, YouTube, URLs, and web tools.
- Spotify and Apple Music: music launching/search workflows.
- Steam: library import and app ID launching.
- Home Assistant: free smart-home control through a local Home Assistant server.
- Discord: bot/status/reminder expansion if you provide a bot token.
- GitHub: issues, pull requests, commits, and project status if you provide a token.
- OpenWeather: weather and air-quality expansion with a free-tier key.
- Todoist: tasks and projects with a Todoist token.
- OBS Studio: local recording/streaming control through OBS WebSocket.
- VS Code and Godot: coding/game-dev workflows and project monitoring.

Optional `.env` names:

```env
HOME_ASSISTANT_URL=http://homeassistant.local:8123
HOME_ASSISTANT_TOKEN=your_home_assistant_long_lived_token
DISCORD_BOT_TOKEN=your_discord_bot_token
GITHUB_TOKEN=your_github_personal_access_token
OPENWEATHER_API_KEY=your_openweather_key
TODOIST_API_TOKEN=your_todoist_token
OBS_WEBSOCKET_URL=ws://127.0.0.1:4455
```

## Agent Tool System

JARVIS includes an agent-based tool layer for broader tasks that do not have a hardcoded command. Existing direct commands still work, but agent mode lets Gemini plan one approved tool call at a time, observe the result, and continue until the task is done or confirmation is needed.

The approved tools are:

- `take_screenshot`
- `analyze_screen`
- `get_active_window`
- `click`, `double_click`, `right_click`
- `type_text`
- `press_key`, `hotkey`, `scroll`
- `open_app`, `switch_window`
- `open_url`, `search_web`
- `get_location`, `open_directions`, `get_eta`
- `list_folder`, `open_file`, `create_folder`
- `move_file` with confirmation
- `delete_file` with confirmation
- `empty_recycle_bin` with confirmation
- `play_music`
- `ask_confirmation`
- `cancel_task`

Safety rules:

- JARVIS does not run arbitrary terminal commands.
- Safe tools can run immediately.
- Medium-risk tools can require confirmation, especially when they affect files, settings, typing, browsers, or external apps.
- High-risk tools always require confirmation.
- Deleting files, moving files, entering private info, sending messages, buying things, or changing passwords should never happen without confirmation.
- JARVIS should not say an action succeeded unless a local function or Windows API reports success.

Useful commands:

- `list tools`
- `agent take a screenshot then analyze my screen`
- `use tools open chrome and search web for Python virtual environments`
- `agent get directions to the nearest grocery store`
- `tool mode list folder C:\Users\YourName\Downloads`
- `action history`

## JARVIS Polish Layer

On launch, JARVIS runs a short startup sequence showing and optionally speaking subsystem status:

- Initializing J.A.R.V.I.S.
- Voice system status
- Vision system status
- Mouse control safe mode
- Gemini connection status
- Time-aware greeting using the name entered during first-run setup

After the technical boot animation, first-time users are asked what JARVIS should call them before the main interface becomes active.

Startup diagnostic messages are visual-only by default. `startup_greeting_speak` controls the short spoken greeting, while `startup_sequence_speak` is kept off so JARVIS does not read every subsystem line aloud.

The side status panel includes online/listening/thinking/acting/speaking status, current mode, current window, vision, voice, mouse control, music, last action, last verified action, and risk level.

Use `action history` to see recent action receipts with status, risk level, and the result message.

Modes:

- `normal mode`: balanced default behavior.
- `coding mode`: leaner chatter and project-oriented assistance.
- `school mode`: calmer focus behavior.
- `gaming mode`: performance/music-oriented behavior.
- `focus mode`: brief responses and lighter interruptions.
- `safe mode`: mouse clicks, typing, hotkeys, and file-changing actions require confirmation.

Personality is controlled by `personality.json`, not by API keys. You can edit assistant name, user name, sarcasm level, formality, voice usage, and short action response preference there.

He does **not** execute arbitrary terminal commands from AI responses. Riskier actions such as closing the active window or locking the laptop require a follow-up `confirm`.

Screen vision uses a screenshot of your current display and sends it to Gemini for analysis. Use commands like `look at my screen`, `read my screen`, or `what should I click?`. JARVIS can describe visible UI and suggest where to click, but he will not claim to have clicked anything unless a local action actually does it.

When proactive monitoring is enabled, JARVIS can notice writing-focused windows such as Google Docs, Word, novel drafts, outlines, or chapters and lightly ask whether you want help with dialogue, pacing, worldbuilding, or scene work. This is controlled by `writing_assist_prompt_enabled` and `writing_assist_prompt_cooldown_minutes` in `settings.json`.

Writing review commands can read the active document aloud and then give honest feedback:

- `read my doc out loud and give feedback`
- `review my Google Doc`
- `critique my novel`
- `give feedback on my writing`

JARVIS tries to focus a likely Google Docs, Word, novel, chapter, draft, or manuscript window, copies the document text with Ctrl+A/C, restores your clipboard text afterward, reads the draft aloud, then sends the captured text to Gemini for critique. The feedback covers what worked, what needs work, the strongest moment, and next revision moves. `document_review_max_chars` limits how much text is sent to Gemini for feedback, and `document_read_chunk_chars` controls speech chunk size.

## Customization

The first run creates `settings.json`. You can edit:

- `user_name`
- `preferred_voice_speed`
- `preferred_music_app`
- `music_provider_order`
- `music_open_browser_fallback`
- `playlist_overrides`
- `wake_phrase`
- `theme`
- `ai_provider`
- `auto_select_gemini_model`
- `gemini_model`
- `gemini_fallback_models`
- `openai_model`
- `enable_openai_web_search`
- `speak_responses`
- `tts_backend`
- `preferred_tts_voice_terms`
- `apple_music_ui_automation`
- `apple_music_result_wait_seconds`
- `apple_music_use_vision_play_button`
- `apple_music_click_first_result`
- `apple_music_text_match_click`
- `proactive_monitoring_enabled`
- `proactive_speak_alerts`
- `monitor_interval_seconds`
- `monitor_alert_cooldown_seconds`
- `internet_alert_failures_required`
- `internet_alert_recoveries_required`
- `cpu_alert_percent`
- `ram_alert_percent`
- `disk_alert_percent`
- `battery_low_percent`
- `work_session_reminder_minutes`
- `awareness_quiet_hours_enabled`
- `awareness_quiet_hours_start`
- `awareness_quiet_hours_end`
- `project_watcher_enabled`
- `project_watch_interval_seconds`
- `project_watch_folders`
- `project_watch_extensions`
- `project_watch_error_terms`
- `agent_tools_enabled`
- `agent_max_steps`
- `agent_require_confirmation_for_medium`
- `location_enabled`
- `location_provider`
- `manual_location`
- `manual_location_label`
- `startup_location_coordinates`
- `allow_ip_location_lookup`
- `auto_update_location_on_startup`
- `startup_location_provider`
- `directions_travel_mode`
- `assistant_mode`
- `mouse_control_mode`
- `command_center_core_visible`
- `command_center_chat_visible`
- `command_center_side_visible`
- `mission_templates`
- `startup_sequence_enabled`
- `startup_sequence_speak`
- `startup_greeting_speak`
- `short_action_responses`
- `integrations`
- `home_assistant_url`
- `obs_websocket_url`
- `custom_app_paths`
- `steam_games`

Do not put API keys or passwords in `settings.json`.

When running the packaged `.exe`, JARVIS stores editable settings and explicit memories in your Windows app-data folder so manually added apps, Steam games, and memories survive app rebuilds. It does not save the chat transcript.

When `auto_select_gemini_model` is `true`, JARVIS checks the Gemini models your key can see when the app starts, picks the newest usable Flash-style text model, and falls back to older models if the selected one hits quota or availability limits.

To customize app launching, edit `custom_app_paths` in `settings.json`. Use the full path to the app's `.exe` or Start Menu `.lnk` shortcut. Example:

```json
"custom_app_paths": {
  "godot": "C:\\Users\\YourName\\Downloads\\Godot_v4.4.1-stable_win64.exe",
  "visual studio code": "",
  "chrome": "",
  "spotify": "",
  "apple music": ""
}
```

The app launcher is intentionally whitelisted so the assistant cannot run arbitrary terminal commands.

You can also add apps from inside JARVIS:

1. Click **Apps**.
2. Enter a name, such as `Blender`.
3. Browse to a real `.exe` or Start Menu `.lnk`.
4. Click **Add To Whitelist**.
5. Use commands like `open blender`.

To customize what JARVIS picks when you say `play music, you pick`, edit `playlist_overrides` in `settings.json`. Supported categories are `coding`, `gamedev`, `browser`, `study`, `gaming`, `creative`, and `general`.

```json
"playlist_overrides": {
  "coding": {
    "label": "my coding playlist",
    "url": "https://www.youtube.com/results?search_query=my+coding+playlist",
    "spotify_uri": "spotify:search:my%20coding%20playlist"
  }
}
```

Apple Music note: the Windows Apple Music app does not expose a reliable public local API for "play this exact searched song" control. JARVIS uses the most practical free path: launch Apple Music, search, use screen vision/UI automation to select the best match, click Play, and verify playback. A more direct integration would require a different provider with playback APIs, classic iTunes COM support for local/library tracks, or a MusicKit web player setup with Apple developer credentials.

You can save explicit memories without saving chat:

- Click **Memory** and add a memory manually.
- Or type `remember that I prefer short answers`.
- Use `what do you remember` to list saved memories.
- Use `forget short answers` or `clear memories` to remove them.

Steam games are whitelisted separately because Steam launches games by App ID:

1. Click **Apps**.
2. Under **Steam Games**, click **Import Library** to scan installed Steam games automatically.
3. Or enter the game name and Steam App ID manually.
4. Click **Add Game** if adding manually.
5. Use commands like `launch Stardew Valley on Steam`.

You can find a game's App ID in its Steam store page URL. For example, `https://store.steampowered.com/app/413150/Stardew_Valley/` uses App ID `413150`.

Apple Music from the Microsoft Store is controlled with best-effort Windows UI automation plus screen vision. JARVIS searches Apple Music, inspects the visible results with Gemini vision, clicks the visually verified matching song result, then inspects the screen again and clicks the visible Play button if it can verify one. If he cannot verify a match or a safe Play button, he refuses to press Play so he does not start a random song.

If vision points too close to the right edge of Apple Music, JARVIS treats that as the scrollbar and redirects the click to a safer point inside the matching song row.

To customize music, edit `PLAYLISTS` in `jarvis.py`. The current URLs are safe placeholder YouTube searches and Spotify search URIs you can replace with your favorite playlist links.

## Safety Notes

JARVIS does not execute commands generated by the AI. Local actions are handled by Python functions and whitelisted command handlers. Risky features such as deleting files, shutting down, restarting, or closing apps are intentionally not implemented by default.
