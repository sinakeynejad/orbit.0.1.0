# Installed Ollama models

Open Settings and choose Ollama. Orbit loads installed model names from the current Base URL (default http://127.0.0.1:11434). Select a model, optionally test the connection, then Save settings. Refresh models reloads the list after an external installation. The manual model field remains available. Changing the URL or closing settings cancels stale list requests.

This feature only lists models; it does not download models or guarantee their support for agent tools. Network requests have a ten-second deadline and do not include saved API keys.

API reference: https://github.com/ollama/ollama/blob/main/docs/api.md (GET /api/tags).
Validation: 61 backend tests, TypeScript check, production UI build; model discovery tested with mocked server responses for success, empty list, malformed output, timeout, rejected request and unreachable server.
