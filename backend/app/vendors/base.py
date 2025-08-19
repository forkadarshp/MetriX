from typing import Any, Dict


class VendorAdapter:
    """Base class for vendor adapters (TTS/STT)."""

    async def synthesize(self, text: str, voice: str = "default", **params) -> Dict[str, Any]:
        raise NotImplementedError

    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        raise NotImplementedError


