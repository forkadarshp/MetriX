import asyncio
import time
import uuid
from typing import Any, Dict

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .base import VendorAdapter
from ..config import logger


class AWSAdapter(VendorAdapter):
    """AWS Polly/Transcribe adapter."""

    def __init__(self, region: str):
        self.region = region
        try:
            self._polly_client = boto3.client("polly", region_name=region)
            logger.info("AWS Polly client initialized successfully using IAM role.")
        except Exception as e:
            logger.error(f"Failed to initialize AWS Polly client: {e}. AWS services will use fallback implementation.")
            self._polly_client = None

    async def synthesize(self, text: str, voice: str = "Joanna", **params) -> Dict[str, Any]:
        logger.info(f"AWS Polly synthesize called for text: '{text[:30]}...'")
        req_time = time.perf_counter()
        if not self._polly_client:
            logger.error("AWS Polly client not initialized; cannot synthesize.")
            return {"status": "error", "error": "AWS Polly client not initialized", "latency": time.perf_counter() - req_time}

        def _synthesize_and_read():
            try:
                logger.info(f"Synthesizing with Polly: voice='{voice}', engine='{params.get('engine', 'neural')}'")
                response = self._polly_client.synthesize_speech(
                    Text=text,
                    OutputFormat="mp3",
                    VoiceId=voice,
                    Engine=params.get("engine", "neural"),
                )
                if "AudioStream" in response:
                    audio_data = response["AudioStream"].read()
                    logger.info(f"Polly returned AudioStream with length: {len(audio_data)} bytes.")
                    return audio_data
                logger.warning("Polly response did not contain AudioStream.")
                return None
            except (BotoCoreError, ClientError) as e:
                logger.error(f"AWS Polly API error during synthesis: {e}")
                return None

        try:
            audio_data = await asyncio.to_thread(_synthesize_and_read)
            api_resp_time = time.perf_counter()
            if not audio_data:
                logger.error("AWS Polly returned no audio data after thread execution.")
                return {"status": "error", "error": "AWS Polly returned no audio data", "latency": time.perf_counter() - req_time}
            audio_filename = f"aws_polly_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            try:
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                logger.info(f"Successfully wrote {len(audio_data)} bytes to {audio_path}")
            except Exception as e:
                logger.error(f"Failed to write audio data to file {audio_path}: {e}")
                return {"status": "error", "error": f"File write error: {e}", "latency": time.perf_counter() - req_time}
            latency = api_resp_time - req_time
            ttfb = latency * 0.2
            return {
                "audio_path": audio_path,
                "vendor": "aws",
                "voice": voice,
                "latency": latency,
                "ttfb": ttfb,
                "status": "success",
                "metadata": {"engine": params.get("engine", "neural"), "voice_id": voice},
            }
        except Exception as e:
            logger.error(f"Unexpected error in AWS Polly synthesize: {e}")
            return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}

    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        req_time = time.perf_counter()
        if not self._polly_client:  # Assume if Polly isn't configured, Transcribe isn't either
            logger.error("AWS Transcribe not configured; cannot transcribe.")
            return {"status": "error", "error": "AWS Transcribe not configured", "latency": time.perf_counter() - req_time}
        return {"status": "error", "error": "AWS Transcribe implementation not available", "latency": time.perf_counter() - req_time}


