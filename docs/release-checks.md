# Release checks

Automated: pytest suite, TypeScript type check, Vite production build, PyInstaller bundle,
desktop startup smoke test. Browser QA: local test provider, approval displayed before action,
approval accepted, response rendered. Native WebView window was opened and visually inspected.

Before claiming production readiness, manually verify with configured real services:
- Ollama text plus tool calling and OpenAI text plus tool calling.
- Persian microphone transcript, playback, microphone denied/unavailable, cloud quota exhausted.
- Correct operation paths/allowlist, confirm/deny/cancel, app relaunch with persisted history.
- Install/run on a clean Windows machine, WebView2 detection and signed packaging.
- Security review of local secret storage, untrusted tool content, path races and request limits.

No real API key, audio recording or cloud model request was used during automated verification.
