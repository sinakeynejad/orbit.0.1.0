# Bugfix verification — 2026-09-27

Fixed: malformed confirmation payload disconnect; uncontrolled session-capacity error; settings disk failure leaking the replacement provider; mislabeled audio uploads; incomplete Ollama tool responses; unsaved settings remaining in the UI; late voice playback/transcription after Stop; stale history after switching conversations; reconnect when selecting the current conversation.

Validation:
- Backend: 30 tests passed, including 5 regressions reproduced before fixes.
- Frontend: 3 cancellation/stale-response tests passed; TypeScript and Vite build passed.
- Isolated browser test: cancel settings restores the saved model, new conversation, approve tool, completion, reopen conversation/history; no browser console errors.
- Packaged Orbit.exe --smoke-test: exit 0.

Model and speech network responses were mocked. Real provider credentials, microphone capture and live speech playback were not exercised in this pass.
