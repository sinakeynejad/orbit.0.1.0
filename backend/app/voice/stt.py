import httpx
from app.core.exceptions import AssistantError
from app.voice.audio import SpeechToText


class OpenAISpeechToText(SpeechToText):
    def __init__(self, settings):
        self.settings = settings

    async def transcribe(self, data, filename):
        key = self.settings.speech_api_key
        if not key:
            raise AssistantError("Voice needs a voice API key in Settings.")
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post("https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": "Bearer " + key.get_secret_value()},
                    data={"model": self.settings.stt_model}, files={"file": (filename, data)})
                response.raise_for_status()
                text = response.json()["text"]
                if not isinstance(text, str) or not text.strip():
                    raise ValueError("Invalid transcription")
                return text
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AssistantError("Transcription failed. Check the voice API key, model and network.") from exc
