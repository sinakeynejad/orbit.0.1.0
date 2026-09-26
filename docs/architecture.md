# Architecture

React UI -> loopback FastAPI REST/WebSocket -> Assistant -> Orchestrator -> LLMProvider ->
ToolRegistry -> ToolExecutor -> OS. The frontend never holds model credentials after a settings
save; credentials are passed to the backend and stored locally. The shell authenticates the page
with a random per-launch token in a URL fragment, cleared before loading protected data. An
HttpOnly SameSite=Strict cookie authenticates browser requests; bearer auth remains available.
Host and Origin are checked. Assets are public on loopback; API routes require authentication.

OpenAI/Ollama implement a provider-neutral Message/ToolCall contract. STT/TTS interfaces are
independent; the current implementation uses OpenAI audio endpoints. SQLite holds complete turns
and tool activity. A failed/interrupted run records completed operations and supplies explicit
unknown results for unresolved calls so history does not silently erase side effects.

SAFE reads execute directly; CONFIRM operations require a matching one-use confirmation bound
to the exact server-side tool arguments. Cancellation stops model waits and unapproved calls;
active synchronous operations finish before the session lock is released.

Desktop shell decision: pywebview replaces the proposed Tauri packaging for this release,
sharing the Python runtime and using the installed WebView2 engine. React and API remain
independent, allowing a future Tauri shell without rewriting agent logic.

Official references used for adapters:
- https://docs.ollama.com/api/chat
- https://developers.openai.com/api/reference/resources/chat
- https://developers.openai.com/api/docs/guides/speech-to-text
- https://developers.openai.com/api/docs/guides/text-to-speech

Security limits, storage policy and roadmap are listed in README.md.
