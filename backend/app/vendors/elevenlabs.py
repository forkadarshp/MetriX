import time
import uuid
from typing import Any, Dict

from .base import VendorAdapter
from ..config import logger
from ..utils import validate_confidence


class ElevenLabsAdapter(VendorAdapter):
    """ElevenLabs TTS/STT adapter."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def synthesize(self, text: str, voice: str = "21m00Tcm4TlvDq8ikWAM", model_id: str = "eleven_flash_v2_5", **params) -> Dict[str, Any]:
        req_time = time.perf_counter()
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {"status": "error", "error": "ElevenLabs API key not configured", "latency": time.perf_counter() - req_time}
        try:
            from elevenlabs import ElevenLabs  # type: ignore
            client = ElevenLabs(api_key=self.api_key)
            req_time = time.perf_counter()
            audio_generator = client.text_to_speech.convert(text=text, voice_id=voice, model_id=model_id)
            audio_chunks = []
            ttfb = None
            for chunk in audio_generator:
                if ttfb is None:
                    ttfb = time.perf_counter() - req_time
                audio_chunks.append(chunk)
            api_resp_time = time.perf_counter()
            audio_filename = f"elevenlabs_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            with open(audio_path, "wb") as f:
                for chunk in audio_chunks:
                    f.write(chunk)
            latency = api_resp_time - req_time
            ttfb_str = f"{ttfb:.3f}s" if ttfb is not None else "N/A"
            logger.info(f"ElevenLabs TTS API latency: {latency:.3f}s, TTFB: {ttfb_str} for text length: {len(text)}")
            return {
                "audio_path": audio_path,
                "vendor": "elevenlabs",
                "voice": voice,
                "latency": latency,
                "ttfb": ttfb,
                "status": "success",
                "metadata": {"model": model_id, "voice_id": voice},
            }
        except Exception as e:
            logger.error(f"ElevenLabs synthesis error: {e}")
            return {"status": "error", "error": str(e), "latency": 0.0}

    async def transcribe(self, audio_path: str, model_id: str = "scribe_v1", **params) -> Dict[str, Any]:
        req_time = time.perf_counter()
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {"status": "error", "error": "ElevenLabs API key not configured", "latency": time.perf_counter() - req_time}
        try:
            from elevenlabs import ElevenLabs  # type: ignore
            client = ElevenLabs(api_key=self.api_key)
            with open(audio_path, 'rb') as audio_file:
                result = client.speech_to_text.convert(file=audio_file, model_id=model_id)
            transcript = result.text if hasattr(result, 'text') else str(result)
            confidence = validate_confidence(getattr(result, 'confidence', 0.95), "elevenlabs")
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "elevenlabs",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model_id},
            }
        except Exception as e:
            logger.error(f"ElevenLabs transcription error: {e}")
            return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}


