<!-- Copilot / AI agent instructions tailored to this repository -->
# Copilot Instructions — AI-Intelligent-Visual-Humanoid-Robot-for-Social-Good-Azure

This file contains short, actionable guidance for AI coding agents working on this repository. Focus on changes that are minimal, safe, and consistent with existing patterns.

1) Big picture (how pieces fit together)
- Entry point(s): `app_startup.py` (recommended for local runs) and `app_main.py` (core app). `app_startup.py` wraps checks and runs `socketio.run()`.
- Web / realtime layer: Flask + Flask-SocketIO (`app_main.py`, `app_socket_handlers.py`). The front-end connects over Socket.IO and uses events like `text_input`, `start_recording`, `start_phone_mode`, `camera_stream`.
- Audio & STT/TTS: `app_audio.py` (TTS via Azure Speech, transcribe via `whisper_selector`/`stt_selector`), `pc_recorder.py`, `audio_manager.py` (higher-level audio helper).
- Vision: `app_vision.py` calls Azure Vision via `vision_client` and delegates text generation to `chatbot.py`. Vision is triggered either by user commands or by `should_trigger_vision()` heuristic in `app_main.py`.
- Robot control: `app_robot_control.py` constructs `curl` commands to the robot HTTP API (hard-coded example IPs: `192.168.149.1:9030`, `192.168.137.3:9030`). The web UI emits socket events that are forwarded to connected robots via `connected_robots`.

2) Developer workflows & commands (Windows / PowerShell)
- Recommended Python: 3.12.6 (project README). Create & activate venv:
```
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```
- Build tools: On Windows install Microsoft Visual C++ Build Tools (required for `PyAudio`, `webrtcvad`, etc.).
- Run locally (recommended):
```
# quick start (uses checks and logs to app.log)
python app_startup.py
# alternative direct run (developer mode)
python app_main.py
```
- `app_startup.py` accepts `host`, `port`, `debug` and `--force`/`--no-force`. Example: `python app_startup.py 0.0.0.0 5001 True --force`

3) Environment & secrets
- Put API keys into a `.env` file or environment variables. Relevant keys in `config.py`: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_SPEECH_API_KEY`, `AZURE_SPEECH_REGION`, `AZURE_VISION_ENDPOINT`, `AZURE_VISION_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`.

4) Project-specific patterns and conventions (important for edits)
- Circular imports are common; modules often import from `app_main` at runtime (e.g., `from app_main import chat_history, stt_selector`). Prefer adding imports inside functions to avoid import-time cycles.
- TTS files: `generate_tts()` writes to `static/response_YYYYMMDDHHMMSS.wav` and returns a path prefixed with `/`. Code expects this naming and format — preserve it when changing TTS behavior.
- Vision trigger: `should_trigger_vision(text)` contains Cantonese/Chinese trigger keywords (see `app_main.py`). Use the same function when adding new triggers.
- Robot actions: The project sends robot actions via HTTP `curl` commands built in `app_robot_control.py`. If you change endpoints, update all hard-coded IPs or centralize them in `config.py` first.
- Whisper selector: `whisper_selector.py` exposes `SpeechToTextSelector` used as `stt_selector`. Mode switching (local vs azure) is done via `stt_selector.switch_mode()` and `update_whisper_settings` API.

5) Useful API endpoints & socket events for testing
- HTTP test endpoints:
  - `POST /api/test/upload-image` (form `image`), `POST /api/test/upload-audio` (form `audio`)
  - `GET /api/test/whisper-status` — checks STT status and Azure creds
  - `POST /execute_singledigit_action` and `/execute_doubledigit_action` — body: `{ "params": ["9","1"] }`
- Useful Socket.IO events (frontend ↔ server): `text_input`, `start_recording`, `start_phone_mode`, `stop_phone_mode`, `control_action`, `camera_stream`, `analyze_camera_frame`.

6) Editing guidance for Copilot / AI agents
- Keep changes minimal: follow existing logging and error-handling style (lots of try/except and logging). Avoid broad refactors unless requested.
- Avoid moving behavior that changes runtime circular imports; if centralizing configuration, place new values in `config.py` and read via `os.getenv()`.
- When changing network/robot endpoints, update both `app_robot_control.py` and any direct `curl` calls in `app_main.py`/`app_vision.py`.
- Preserve `static/` and `uploads/` file layout; startup cleans some generated files — do not assume persistence of `static/response_*.wav` across restarts.

7) Quick examples (copy-paste)
- Start server (PowerShell):
```
python app_startup.py
```
- Trigger a single robot action via curl (example):
```
curl -X POST http://localhost:5001/execute_singledigit_action -H "Content-Type: application/json" -d "{\"params\": [\"9\", \"1\"]}"
```
- Call vision-triggering text via SocketIO `text_input` event: send `{ "text": "你看到什麼" }` to trigger camera analysis.

8) Where to look first when debugging
- Logs: `app.log` (created by startup), and console output. Many modules use `logging` and `print` for debug.
- Startup checks: `app_startup.py` (dependency & config checks) and `requirements.txt` for needed packages.
- STT/TTS problems: `app_audio.py`, `whisper_selector.py`, and `config.py` for keys. On Windows, missing build tools often cause install/runtime errors for audio packages.

If anything here is unclear or you want more detail on a section (e.g., call flows for phone mode, or how `chatbot.py` is wired), tell me which area to expand and I will iterate.
