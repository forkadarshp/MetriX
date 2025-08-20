import time
import uuid
from typing import Any, Dict

import aiofiles

from .base import VendorAdapter
from ..config import logger, debug_log


class AzureOpenAIAdapter(VendorAdapter):
    """Azure OpenAI Whisper STT adapter using pipecat."""

    def __init__(self, api_key: str, endpoint: str, api_version: str = "2024-06-01", model: str = "whisper-1"):
        self.api_key = api_key
        self.endpoint = endpoint
        self.api_version = api_version
        self.model = model
        self._stt_service = None
        self._initialized = False

    def _initialize_services(self):
        """Lazy initialization of pipecat services."""
        if self._initialized:
            return
        
        try:
            from pipecat.services.openai.stt import OpenAISTTService
            from openai import AsyncAzureOpenAI
            
            # Initialize the STT service
            self._stt_service = OpenAISTTService(
                model=self.model, 
                api_key=self.api_key
            )
            
            # Create Azure OpenAI client
            stt_client_azure = AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                api_key=self.api_key
            )
            
            # Override the client in the STT service
            self._stt_service._client = stt_client_azure
            self._initialized = True
            logger.info("Azure OpenAI STT service initialized successfully")
            
        except ImportError as e:
            logger.error(f"Required packages not installed for Azure OpenAI: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI STT service: {e}")
            raise

    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        """Transcribe audio using Azure OpenAI Whisper."""
        req_time = time.perf_counter()
        
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {
                "status": "error", 
                "error": "Azure OpenAI API key not configured", 
                "latency": time.perf_counter() - req_time
            }

        if not self.endpoint or self.endpoint.lower().startswith("dummy"):
            return {
                "status": "error", 
                "error": "Azure OpenAI endpoint not configured", 
                "latency": time.perf_counter() - req_time
            }

        try:
            # Initialize services if not already done
            if not self._initialized:
                self._initialize_services()

            # Read the audio file
            async with aiofiles.open(audio_path, 'rb') as audio_file:
                audio_data = await audio_file.read()

            debug_log(f"Azure OpenAI transcribing audio file: {audio_path} ({len(audio_data)} bytes)")

            # Use the pipecat STT service for transcription
            # Note: This is a simplified implementation as pipecat's STT service
            # is typically used in streaming contexts, but we adapt it for file transcription
            from openai import AsyncAzureOpenAI
            
            client = AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                api_key=self.api_key
            )

            # Create a temporary file-like object for the OpenAI API
            import io
            audio_file_obj = io.BytesIO(audio_data)
            audio_file_obj.name = audio_path  # OpenAI API needs a name attribute

            # Call the Azure OpenAI transcription API
            language = params.get("language", "en")
            prompt = params.get("prompt", "")
            temperature = params.get("temperature", 0)
            
            response = await client.audio.transcriptions.create(
                model=self.model,
                file=audio_file_obj,
                language=language if language != "auto" else None,
                prompt=prompt if prompt else None,
                temperature=temperature
            )

            transcript = response.text
            latency = time.perf_counter() - req_time

            logger.info(f"Azure OpenAI transcription completed: {len(transcript)} chars in {latency:.3f}s")

            return {
                "transcript": transcript,
                "confidence": 1.0,  # Azure OpenAI doesn't provide confidence scores
                "vendor": "azure_openai",
                "latency": latency,
                "status": "success",
                "metadata": {
                    "model": self.model,
                    "language": language,
                    "endpoint": self.endpoint
                },
            }

        except Exception as e:
            logger.error(f"Azure OpenAI transcription error: {e}")
            return {
                "status": "error", 
                "error": str(e), 
                "latency": time.perf_counter() - req_time
            }

    async def synthesize(self, text: str, voice: str = "alloy", **params) -> Dict[str, Any]:
        """Synthesize speech using Azure OpenAI TTS."""
        req_time = time.perf_counter()
        
        api_key = (self.api_key or "").strip()
        if not api_key or api_key.lower().startswith("dummy"):
            return {
                "status": "error", 
                "error": "Azure OpenAI API key not configured", 
                "latency": time.perf_counter() - req_time
            }

        if not self.endpoint or self.endpoint.lower().startswith("dummy"):
            return {
                "status": "error", 
                "error": "Azure OpenAI endpoint not configured", 
                "latency": time.perf_counter() - req_time
            }

        try:
            from openai import AsyncAzureOpenAI
            
            client = AsyncAzureOpenAI(
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
                api_key=self.api_key
            )

            model = params.get("model", "tts-1")
            response_format = params.get("response_format", "mp3")
            speed = params.get("speed", 1.0)

            debug_log(f"Azure OpenAI TTS synthesis: model={model}, voice={voice}, format={response_format}")

            # Call the Azure OpenAI TTS API
            response = await client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                response_format=response_format,
                speed=speed
            )

            # Generate a unique filename
            file_ext = response_format if response_format in ["mp3", "wav", "flac"] else "mp3"
            audio_filename = f"azure_openai_tts_{uuid.uuid4().hex}.{file_ext}"
            audio_path = f"storage/audio/{audio_filename}"

            # Save the audio data
            audio_data = b""
            async for chunk in response.iter_bytes(chunk_size=1024):
                audio_data += chunk

            async with aiofiles.open(audio_path, 'wb') as f:
                await f.write(audio_data)

            latency = time.perf_counter() - req_time
            ttfb = latency * 0.1  # Estimate first byte time

            logger.info(f"Azure OpenAI TTS synthesis completed: {len(audio_data)} bytes in {latency:.3f}s")

            return {
                "audio_path": audio_path,
                "vendor": "azure_openai",
                "voice": voice,
                "latency": latency,
                "ttfb": ttfb,
                "status": "success",
                "duration": 0.0,  # Could calculate if needed
                "metadata": {
                    "model": model,
                    "voice": voice,
                    "response_format": response_format,
                    "speed": speed,
                    "file_size": len(audio_data)
                },
            }

        except Exception as e:
            logger.error(f"Azure OpenAI TTS synthesis error: {e}")
            return {
                "status": "error", 
                "error": str(e), 
                "latency": time.perf_counter() - req_time
            }
