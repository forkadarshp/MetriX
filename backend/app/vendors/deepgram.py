import time
import uuid
from typing import Any, Dict

import aiofiles
import httpx

from .base import VendorAdapter
from ..config import logger, debug_log


class DeepgramAdapter(VendorAdapter):
    """Deepgram STT/TTS adapter."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def transcribe(self, audio_path: str, model: str = "nova-3", **params) -> Dict[str, Any]:
        req_time = time.perf_counter()
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {"status": "error", "error": "Deepgram API key not configured", "latency": time.perf_counter() - req_time}
        try:
            from deepgram import DeepgramClient, PrerecordedOptions, FileSource  # type: ignore
            client = DeepgramClient(self.api_key)
            smart_format = bool(params.get("smart_format", True))
            punctuate = bool(params.get("punctuate", True))
            language = params.get("language", "en-US")
            options = PrerecordedOptions(model=model, smart_format=smart_format, punctuate=punctuate, language=language)
            with open(audio_path, 'rb') as audio_file:
                buffer_data = audio_file.read()
            payload: FileSource = {"buffer": buffer_data}
            response = client.listen.prerecorded.v("1").transcribe_file(payload, options)
            transcript = response.results.channels[0].alternatives[0].transcript
            confidence = response.results.channels[0].alternatives[0].confidence
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "deepgram",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model, "language": "en-US"},
            }
        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}

    async def synthesize(self, text: str, model: str = "aura-2", voice: str = "thalia", container: str = "mp3", sample_rate: int = 24000, **params) -> Dict[str, Any]:
        debug_log(f"Deepgram synthesize called with: model={model}, voice={voice}, container={container}, sample_rate={sample_rate}, params={params}")
        req_time = time.perf_counter()
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {"status": "error", "error": "Deepgram API key not configured", "latency": time.perf_counter() - req_time}
        try:
            url = "https://api.deepgram.com/v1/speak"
            headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}
            if model == "aura-2" and voice:
                combined_model = f"aura-2-{voice}-en"
            else:
                combined_model = model
            if container == "wav":
                params = {"model": combined_model, "encoding": "linear16", "container": "wav", "sample_rate": str(sample_rate)}
            else:
                params = {"model": combined_model, "encoding": "mp3", "bit_rate": "48000"}
                container = "mp3"
            payload = {"text": text}
            file_ext = "wav" if container == "wav" else "mp3"
            audio_filename = f"deepgram_tts_{uuid.uuid4().hex}.{file_ext}"
            audio_path = f"storage/audio/{audio_filename}"
            req_time = time.perf_counter()
            ttfb = None
            file_size = 0
            audio_chunks = []
            async with httpx.AsyncClient() as client:
                logger.info(f"Deepgram TTS request: {url} with params: {params} and payload: {payload}")
                async with client.stream("POST", url, headers=headers, params=params, json=payload, timeout=60.0) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        logger.error(f"Deepgram TTS error response: {resp.status_code} - {error_text.decode()}")
                        return {"status": "error", "error": f"HTTP {resp.status_code}: {error_text.decode()}", "latency": 0.0}
                    async for chunk in resp.aiter_bytes(chunk_size=1024):
                        if ttfb is None:
                            ttfb = time.perf_counter() - req_time
                        audio_chunks.append(chunk)
                        file_size += len(chunk)
                    api_resp_time = time.perf_counter()
            async with aiofiles.open(audio_path, 'wb') as f:
                for chunk in audio_chunks:
                    await f.write(chunk)
            latency = api_resp_time - req_time
            duration = 0.0
            if container == "wav" and file_size > 44:
                mono_bps = int(sample_rate) * 2
                stereo_bps = int(sample_rate) * 2 * 2
                audio_bytes = file_size - 44
                mono_duration = audio_bytes / mono_bps
                stereo_duration = audio_bytes / stereo_bps
                if 1.0 <= stereo_duration <= 10.0:
                    duration = stereo_duration
                    debug_log(f"Using stereo duration: {duration:.3f}s")
                elif 1.0 <= mono_duration <= 10.0:
                    duration = mono_duration
                    debug_log(f"Using mono duration: {duration:.3f}s")
                else:
                    duration = stereo_duration
                    debug_log(f"Both durations unrealistic, defaulting to stereo: {duration:.3f}s")
                debug_log(f"Deepgram WAV duration calc: file_size={file_size}, audio_bytes={audio_bytes}, sample_rate={sample_rate}, mono_dur={mono_duration:.3f}s, stereo_dur={stereo_duration:.3f}s, chosen={duration:.3f}s")
            ttfb_str = f"{ttfb:.3f}s" if ttfb is not None else "N/A"
            logger.info(f"Deepgram TTS API latency: {latency:.3f}s, TTFB: {ttfb_str}, duration: {duration:.3f}s for text length: {len(text)}")
            return {
                "audio_path": audio_path,
                "vendor": "deepgram",
                "latency": latency,
                "ttfb": ttfb,
                "status": "success",
                "duration": duration,
                "metadata": {"model": model, "container": container, "sample_rate": sample_rate, "file_size": file_size},
            }
        except Exception as e:
            logger.error(f"Deepgram TTS error: {e}")
            return {"status": "error", "error": str(e), "latency": 0.0}


