from abc import ABC, abstractmethod


class SpeechToText(ABC):
    @abstractmethod
    async def transcribe(self, data: bytes, filename: str) -> str: ...


class TextToSpeech(ABC):
    @abstractmethod
    async def speak(self, text: str) -> bytes: ...
