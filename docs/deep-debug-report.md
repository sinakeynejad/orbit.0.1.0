# Debug pass

Fixed failures reproduced by regression tests:
- Saved model credentials could follow an edited provider endpoint without re-entry.
- Malformed provider responses escaped controlled error handling.
- One invalid stored conversation prevented loading all history; invalid records are now preserved and skipped with a diagnostic log.
- Session creation/deletion changed memory before storage succeeded.
- Windows case-insensitive .TRASH paths bypassed the reserved-directory guard.

Additional corrections:
- Voice only reuses model credentials for the official OpenAI endpoint; other providers require a separate voice key.
- Invalid transcription output is rejected.
- Storage errors return a usable message.
- Search refresh reads the current query and ignores aborted requests.
- History reloads after reconnect/completion/cancellation/error.
- Old sockets cannot update the selected conversation.
- Duplicate conversation creation is guarded; creating one clears search filters.
- IME composition does not accidentally send a message.
- Disabled sending/voice controls have visible setup guidance.
- Markdown downloads use a stable authenticated attachment URL instead of a short-lived blob.

Validation: 76 backend tests passed; 6 frontend tests passed; TypeScript and Vite build passed. Isolated browser flow verified creation, cleared search, sending, denying a tool, synchronized formatted response, and actual Markdown download. Browser error log was empty. Live provider credentials, real microphone/audio and every native OS integration were not exercised. This is a tested debugging pass, not a guarantee of zero remaining defects.
