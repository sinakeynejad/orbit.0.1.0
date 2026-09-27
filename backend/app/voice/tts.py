import httpx
from app.core.exceptions import AssistantError
from app.voice.audio import TextToSpeech


class OpenAITextToSpeech(TextToSpeech):
    def __init__(self, settings):
        self.settings = settings

    async def speak(self, text):
        key = self.settings.speech_api_key
        if not key:
            raise AssistantError("Voice needs a voice API key in Settings.")
        try:
            async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
                response = await client.post("https://api.openai.com/v1/audio/speech",
                    headers={"Authorization": "Bearer " + key.get_secret_value()},
                    json={"model": self.settings.tts_model, "voice": "alloy", "input": text, "response_format": "mp3"})
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as exc:
            raise AssistantError("Speech generation failed. Check voice settings and network.") from exc
