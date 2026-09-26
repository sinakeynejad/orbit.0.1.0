# Orbit — Desktop AI Assistant

A Windows desktop assistant built with React + TypeScript, FastAPI and Python 3.12.
The desktop shell uses **pywebview / WebView2**, not Tauri. The Python service binds to
an ephemeral loopback port; the UI accesses it through authenticated REST/WebSocket.

## Run the packaged app

Open `dist/Orbit/Orbit.exe`. Keep the entire `Orbit` directory together: `_internal`
contains the runtime and bundled frontend. Python/Node are not needed for this build.
Windows must have Microsoft Edge WebView2 Runtime. This is an unsigned development
build, not a signed installer. Do not disable Windows security protections to run it.

1. Open **Settings** and choose Ollama (local) or OpenAI (cloud).
2. Enter the exact installed/available tool-capable model name. For OpenAI enter your API key.
3. Optionally configure your workspace and application aliases using absolute `.exe` paths.
4. Create a conversation, type a request, and review any operation confirmation.
5. Voice requires an OpenAI voice key (or the configured model API key). Record, review the
   transcript, then send it. `Listen` generates an **AI voice**, not a human recording.

No API credentials or local model are included. No paid model calls run automatically.
Model and voice capability depends on the selected service, account and model.

## Implemented

- OpenAI Chat Completions and Ollama adapters with tool-call normalization and timeout/error handling.
- Bounded multi-step agent loop; per-session locks; interruption and confirmation timeouts.
- SQLite conversation persistence and operation activity log.
- System info, directory listing, folder creation, new text files, text reading, copy,
  move, rename and recoverable file deletion inside an explicit workspace.
- Allowlisted `.exe` application launching without shell execution or arbitrary arguments.
- Screen capture to a workspace PNG and clipboard read/write, all requiring approval.
- React chat, session history, settings, status, approvals, activity, microphone recording
  and cloud transcription/speech playback. Persian message text uses automatic direction.
- Native Windows shell and PyInstaller folder distribution.

## Storage and privacy

User settings, history and activity are stored under `%LOCALAPPDATA%/DesktopAssistant`.
The default workspace is its `workspace` subdirectory. API keys currently live in the local
settings JSON file **without encryption**; protect your Windows user account and do not share
that file. The `.env` alternative is supported and excluded from Git. Settings UI values saved
in JSON take priority over `.env` on subsequent starts. API keys are never returned by settings
GET, placed in tool schemas, or bundled in the executable.

Conversation/tool content is sent to the chosen model. Voice recordings are uploaded only on
explicit recording completion; they go to OpenAI. Microphone capture stops after 60 seconds.
Clipboard reads/text-file reads require approval because their content enters model context.
Screenshots are saved locally; this release does not send images to the model for interpretation.
Deletion moves files into `.trash` under the workspace; restore manually in Explorer.
Deleting a conversation removes its saved messages but does not purge the separate activity log.

## Development

Install Python 3.12, Node 22+ and pnpm. From the root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt -r backend/requirements-desktop.txt
pnpm --dir frontend install --frozen-lockfile --ignore-scripts
pnpm --dir frontend build
.\.venv\Scripts\python.exe backend/desktop.py
```

Tests:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

`build.ps1` creates the native folder build. `start.ps1` runs source using the already-built UI.
`backend/desktop.py --smoke-test` starts the server, checks bundled UI, and exits without a window.
`backend/tests/preview_server.py` is an explicit **fake-provider UI test server**, never production.

## Verification and current boundaries

Automated tests cover HTTP serialization, model errors, tool validation, path confinement,
permissions, approval IDs, cancellation, persistence, auth/origin checks and file operations.
The React production build and desktop startup are tested. Live provider calls, microphone
hardware and voice quality require the user's configured credentials/device and are not certified.

This is a development release, **not a guarantee of flawless or production-secure operation**.
Tools are restricted Python functions, not an OS sandbox. Concurrent hostile filesystem writers
can create path races. A running OS operation finishes before cancellation releases the session;
completed operations are not undone. History retains 20 turns; activity shows the last 100 events.
Only one application instance should use the settings/history directory at a time.

Not implemented: OCR engine, browser automation, visual screen understanding, wake word,
semantic long-term memory, token streaming, plugin loading, signed installer and auto-updates.
These were later roadmap capabilities, not silently replaced with mock implementations.

See [architecture](docs/architecture.md), [API](docs/api.md) and [release checks](docs/release-checks.md).
