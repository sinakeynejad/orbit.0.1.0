# API v0.2

Authorization: Bearer <local token>, or HttpOnly cookie obtained by POST /auth with bearer auth.
Only same-origin browser requests are accepted. Do not expose this service on a public interface.

| Endpoint | Purpose |
|---|---|
| GET /health | Backend liveness, not model readiness |
| POST /auth | Exchange bearer token for local session cookie |
| GET/POST /sessions | List/create persistent conversations |
| GET/DELETE /sessions/{id} | Read/delete saved messages |
| POST /sessions/{id}/messages | Send {message}; confirmation-required tools denied on REST |
| GET/PUT /settings | Read redacted config / update provider, workspace, application aliases |
| GET /audit | Last 100 operation events |
| POST /voice/transcribe | Multipart file (maximum 10 MB); returns {text} |
| POST /voice/speak | {text}, maximum 4000 chars; returns audio/mpeg |
| WS /ws?session_id=... | Resume a session or create one if omitted |

Client events: {type:message,message:...}, {type:cancel},
{type:confirmation,confirmation_id:...,approved:true|false}.
Server events: session, thinking, executing, tool_result, confirmation_required,
confirmation_expired, completed, cancelled, error. Confirmations expire after 60 seconds.
No token-streaming events are emitted. Disconnect cancels active work but keeps conversation.
A synchronous OS operation already started cannot be rolled back by cancelling.

Keys in PUT /settings: omitted/null keeps existing; empty string clears the key. Blank UI inputs
currently keep keys; remove them using authenticated API or the local settings file if needed.
Application aliases are editable only through settings; tools cannot edit their own allowlist.
Expected assistant failures use 400, invalid schemas 422, auth failure 401 and rejected Origin 403.
