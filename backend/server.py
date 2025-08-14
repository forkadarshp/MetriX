from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any, Literal, Union
import os
import uuid
import asyncio
import time
import sqlite3
import json
import tempfile
import aiofiles
import httpx
from datetime import datetime, timedelta
import logging
from pathlib import Path
import traceback
from dotenv import load_dotenv
import io
import csv
import wave

# Try optional audio duration reader
try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import jiwer for accurate WER calculation
try:
    import jiwer
    JIWER_AVAILABLE = True
except ImportError:
    JIWER_AVAILABLE = False
    logger.warning("jiwer not available - using fallback WER calculation (less accurate)")

# Environment variables
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "dummy_eleven_key")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "dummy_deepgram_key")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", "dummy_aws_key")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", "dummy_aws_secret")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize FastAPI app
app = FastAPI(title="TTS/STT Benchmarking Dashboard", version="1.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if CORS_ORIGINS == "*" else CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create data directory and storage
os.makedirs("data", exist_ok=True)
os.makedirs("storage/audio", exist_ok=True)
os.makedirs("storage/transcripts", exist_ok=True)

# SQLite Database setup
DB_PATH = "data/benchmark.db"

def init_database():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables based on the spec
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS scripts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS script_items (
            id TEXT PRIMARY KEY,
            script_id TEXT NOT NULL,
            text TEXT NOT NULL,
            lang TEXT DEFAULT 'en-US',
            tags TEXT,
            FOREIGN KEY (script_id) REFERENCES scripts (id)
        );
        
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            mode TEXT NOT NULL CHECK (mode IN ('isolated', 'chained')),
            vendor_list_json TEXT NOT NULL,
            config_json TEXT,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects (id)
        );
        
        CREATE TABLE IF NOT EXISTS run_items (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            script_item_id TEXT,
            vendor TEXT NOT NULL,
            text_input TEXT NOT NULL,
            audio_path TEXT,
            transcript TEXT,
            metrics_json TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES runs (id),
            FOREIGN KEY (script_item_id) REFERENCES script_items (id)
        );
        
        CREATE TABLE IF NOT EXISTS metrics (
            id TEXT PRIMARY KEY,
            run_item_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            threshold REAL,
            pass_fail TEXT CHECK (pass_fail IN ('pass', 'fail')),
            FOREIGN KEY (run_item_id) REFERENCES run_items (id)
        );
        
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            run_item_id TEXT NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('audio', 'transcript', 'log')),
            file_path TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_item_id) REFERENCES run_items (id)
        );
        
        -- Insert default project and user
        INSERT OR IGNORE INTO users (id, name, role) VALUES ('default_user', 'Default User', 'admin');
        INSERT OR IGNORE INTO projects (id, name, description) VALUES ('default_project', 'Default Project', 'Default benchmarking project');
        
        -- Insert sample scripts
        INSERT OR IGNORE INTO scripts (id, name, description, tags) VALUES 
        ('banking_script', 'Banking Script', 'Banking domain test phrases', 'banking,finance'),
        ('general_script', 'General Script', 'General purpose test phrases', 'general');
        
        INSERT OR IGNORE INTO script_items (id, script_id, text, lang, tags) VALUES 
        ('item_1', 'banking_script', 'Welcome to our banking services. How can I help you today?', 'en-US', 'greeting'),
        ('item_2', 'banking_script', 'Your account balance is one thousand two hundred and fifty dollars.', 'en-US', 'numbers'),
        ('item_3', 'banking_script', 'Please verify your identity by providing your social security number.', 'en-US', 'security'),
        ('item_4', 'general_script', 'The quick brown fox jumps over the lazy dog.', 'en-US', 'pangram'),
        ('item_5', 'general_script', 'Hello world, this is a test of the speech recognition system.', 'en-US', 'test');
    """)
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_database()

# Pydantic models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ScriptCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[str] = None

class ScriptItemCreate(BaseModel):
    script_id: str
    text: str
    lang: str = "en-US"
    tags: Optional[str] = None

class RunCreate(BaseModel):
    project_id: Optional[str] = "default_project"
    mode: Literal["isolated", "chained"]
    vendors: List[str]
    config: Optional[Dict[str, Any]] = {}
    text_inputs: Optional[List[str]] = None
    script_ids: Optional[List[str]] = None

class QuickRunForm(BaseModel):
    text: str
    vendors: List[str]
    mode: Literal["isolated", "chained"]
    config: Optional[Dict[str, Any]] = {}

class MetricResult(BaseModel):
    name: str
    value: float
    unit: Optional[str] = None
    threshold: Optional[float] = None
    pass_fail: Optional[str] = None

# Vendor Adapters
class VendorAdapter:
    """Base class for vendor adapters."""
    
    async def synthesize(self, text: str, voice: str = "default", **params) -> Dict[str, Any]:
        """Synthesize text to speech."""
        raise NotImplementedError
    
    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        """Transcribe audio to text."""
        raise NotImplementedError

class ElevenLabsAdapter(VendorAdapter):
    """ElevenLabs TTS/STT adapter."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.is_dummy = api_key == "dummy_eleven_key"
    
    async def synthesize(self, text: str, voice: str = "21m00Tcm4TlvDq8ikWAM", model_id: str = "eleven_flash_v2_5", **params) -> Dict[str, Any]:
        """Synthesize text using ElevenLabs TTS."""
        req_time = time.perf_counter()
        if self.is_dummy:
            await asyncio.sleep(0.5)  # Simulate API delay
            audio_filename = f"elevenlabs_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            with open(audio_path, "wb") as f:
                f.write(b"dummy_audio_data_elevenlabs")
            resp_time = time.perf_counter()
            return {
                "audio_path": audio_path,
                "vendor": "elevenlabs",
                "voice": voice,
                "latency": resp_time - req_time,  # pure API latency
                "status": "success",
                "metadata": {"model": model_id, "voice_id": voice}
            }
        else:
            try:
                from elevenlabs import ElevenLabs
                client = ElevenLabs(api_key=self.api_key)
                # Generate audio (streamed) and measure until final byte
                audio_generator = client.text_to_speech.convert(
                    text=text,
                    voice_id=voice,
                    model_id=model_id
                )
                audio_filename = f"elevenlabs_{uuid.uuid4().hex}.mp3"
                audio_path = f"storage/audio/{audio_filename}"
                async_write = False
                start_stream = time.perf_counter()
                with open(audio_path, "wb") as f:
                    for chunk in audio_generator:
                        f.write(chunk)
                end_stream = time.perf_counter()
                return {
                    "audio_path": audio_path,
                    "vendor": "elevenlabs",
                    "voice": voice,
                    "latency": end_stream - req_time,  # request to final byte
                    "status": "success",
                    "metadata": {"model": model_id, "voice_id": voice}
                }
            except Exception as e:
                logger.error(f"ElevenLabs synthesis error: {e}")
                return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}
    
    async def transcribe(self, audio_path: str, model_id: str = "scribe_v1", **params) -> Dict[str, Any]:
        """Transcribe audio using ElevenLabs STT (Scribe)."""
        req_time = time.perf_counter()
        if self.is_dummy:
            await asyncio.sleep(0.3)
            return {
                "transcript": "Dummy transcription from ElevenLabs Scribe.",
                "confidence": 0.92,
                "vendor": "elevenlabs",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model_id}
            }
        try:
            from elevenlabs import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)
            with open(audio_path, 'rb') as audio_file:
                result = client.speech_to_text.convert(
                    file=audio_file,
                    model_id=model_id,
                )
            transcript = result.text if hasattr(result, 'text') else str(result)
            confidence = validate_confidence(getattr(result, 'confidence', 0.95), "elevenlabs")
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "elevenlabs",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model_id}
            }
        except Exception as e:
            logger.error(f"ElevenLabs transcription error: {e}")
            return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}

class DeepgramAdapter(VendorAdapter):
    """Deepgram STT/TTS adapter."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.is_dummy = api_key == "dummy_deepgram_key"
    
    async def transcribe(self, audio_path: str, model: str = "nova-3", **params) -> Dict[str, Any]:
        """Transcribe audio using Deepgram STT."""
        req_time = time.perf_counter()
        if self.is_dummy:
            await asyncio.sleep(0.3)
            dummy_transcripts = [
                "Welcome to our banking services. How can I help you today?",
                "Your account balance is one thousand two hundred fifty dollars.",
                "The quick brown fox jumps over the lazy dog.",
                "Hello world, this is a test of the speech recognition system."
            ]
            transcript = dummy_transcripts[hash(audio_path) % len(dummy_transcripts)]
            confidence = 0.85 + (hash(audio_path) % 15) / 100
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "deepgram",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model, "language": "en-US"}
            }
        else:
            try:
                from deepgram import DeepgramClient, PrerecordedOptions, FileSource
                client = DeepgramClient(self.api_key)
                # Raw STT by default (no formatting/punctuation), override via params if needed
                smart_format = bool(params.get("smart_format", False))
                punctuate = bool(params.get("punctuate", False))
                language = params.get("language", "en-US")
                options = PrerecordedOptions(
                    model=model,
                    smart_format=smart_format,
                    punctuate=punctuate,
                    language=language,
                )
                with open(audio_path, 'rb') as audio_file:
                    buffer_data = audio_file.read()
                payload: FileSource = {
                    "buffer": buffer_data,
                }
                response = client.listen.prerecorded.v("1").transcribe_file(
                    payload, options
                )
                transcript = response.results.channels[0].alternatives[0].transcript
                confidence = response.results.channels[0].alternatives[0].confidence
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "vendor": "deepgram",
                    "latency": time.perf_counter() - req_time,
                    "status": "success",
                    "metadata": {"model": model, "language": "en-US"}
                }
            except Exception as e:
                logger.error(f"Deepgram transcription error: {e}")
                return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}

    async def synthesize(self, text: str, model: str = "aura-2", voice: str = "thalia", container: str = "wav", sample_rate: int = 24000, **params) -> Dict[str, Any]:
        """Synthesize speech using Deepgram Speak API (Aura 2).
        Note: Use a containerized format (mp3) to ensure proper duration parsing across environments.
        """
        req_time = time.perf_counter()
        ttfb = None
        if self.is_dummy:
            await asyncio.sleep(0.4)
            audio_filename = f"deepgram_tts_{uuid.uuid4().hex}.{ 'wav' if container == 'wav' else 'ogg' }"
            audio_path = f"storage/audio/{audio_filename}"
            with open(audio_path, "wb") as f:
                f.write(b"dummy_deepgram_tts_audio")
            return {
                "audio_path": audio_path,
                "vendor": "deepgram",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"model": model, "container": container, "sample_rate": sample_rate}
            }
        try:
            url = "https://api.deepgram.com/v1/speak"
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json"
            }
            # Request a proper containerized output (mp3 by default)
            # Deepgram Speak API uses combined model format like "aura-2-thalia-en"
            if model == "aura-2" and voice:
                combined_model = f"aura-2-{voice}-en"
            else:
                combined_model = model
            
            # Deepgram API: For WAV use encoding=linear16&container=wav, for MP3 use encoding=mp3&bit_rate
            if container == "wav":
                params = {
                    "model": combined_model,
                    "encoding": "linear16",
                    "container": "wav",
                    "sample_rate": str(sample_rate)
                }
            else:
                # Default to MP3 with bitrate
                params = {
                    "model": combined_model,
                    "encoding": "mp3",
                    "bit_rate": "48000"  # 48kbps default
                }
                container = "mp3"  # Override for file extension
            payload = {"text": text}
            file_ext = "wav" if container == "wav" else "mp3"
            audio_filename = f"deepgram_tts_{uuid.uuid4().hex}.{file_ext}"
            audio_path = f"storage/audio/{audio_filename}"
            file_size = 0
            async with httpx.AsyncClient() as client:
                logger.info(f"Deepgram TTS request: {url} with params: {params} and payload: {payload}")
                async with client.stream("POST", url, headers=headers, params=params, json=payload, timeout=60.0) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        logger.error(f"Deepgram TTS error response: {resp.status_code} - {error_text.decode()}")
                        return {"status": "error", "error": f"HTTP {resp.status_code}: {error_text.decode()}", "latency": time.perf_counter() - req_time}
                    async with aiofiles.open(audio_path, 'wb') as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024):
                            if ttfb is None:
                                ttfb = time.perf_counter() - req_time
                            await f.write(chunk)
                            file_size += len(chunk)
            return {
                "audio_path": audio_path,
                "vendor": "deepgram",
                "latency": time.perf_counter() - req_time,
                "ttfb": ttfb,
                "status": "success",
                "metadata": {"model": model, "container": container, "sample_rate": sample_rate, "file_size": file_size}
            }
        except Exception as e:
            logger.error(f"Deepgram TTS error: {e}")
            return {"status": "error", "error": str(e), "latency": time.perf_counter() - req_time}

class AWSAdapter(VendorAdapter):
    """AWS Polly/Transcribe adapter using dummy implementation."""
    
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.is_dummy = access_key == "dummy_aws_key"
    
    async def synthesize(self, text: str, voice: str = "Joanna", **params) -> Dict[str, Any]:
        """Synthesize text using AWS Polly."""
        req_time = time.perf_counter()
        if self.is_dummy:
            await asyncio.sleep(0.4)
            audio_filename = f"aws_polly_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            with open(audio_path, "wb") as f:
                f.write(b"dummy_audio_data_aws_polly")
            return {
                "audio_path": audio_path,
                "vendor": "aws_polly",
                "voice": voice,
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"engine": "neural", "voice_id": voice}
            }
        else:
            return {"status": "error", "error": "Real AWS implementation not available", "latency": time.perf_counter() - req_time}
    
    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        """Transcribe audio using AWS Transcribe."""
        req_time = time.perf_counter()
        if self.is_dummy:
            await asyncio.sleep(0.6)
            dummy_transcripts = [
                "Welcome to our banking services how can I help you today",
                "Your account balance is one thousand two hundred fifty dollars",
                "The quick brown fox jumps over the lazy dog",
                "Hello world this is a test of the speech recognition system"
            ]
            transcript = dummy_transcripts[hash(audio_path) % len(dummy_transcripts)]
            confidence = 0.80 + (hash(audio_path) % 20) / 100
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "aws_transcribe",
                "latency": time.perf_counter() - req_time,
                "status": "success",
                "metadata": {"job_name": f"job_{uuid.uuid4().hex}", "language": "en-US"}
            }
        else:
            return {"status": "error", "error": "Real AWS implementation not available", "latency": time.perf_counter() - req_time}

# Initialize vendor adapters
elevenlabs_adapter = ElevenLabsAdapter(ELEVEN_API_KEY)
deepgram_adapter = DeepgramAdapter(DEEPGRAM_API_KEY)
aws_adapter = AWSAdapter(AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION)

VENDOR_ADAPTERS = {
    "elevenlabs": {"tts": elevenlabs_adapter, "stt": elevenlabs_adapter},
    "deepgram": {"tts": deepgram_adapter, "stt": deepgram_adapter},
    "aws": {"tts": aws_adapter, "stt": aws_adapter}
}

# Helper functions
def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Calculate Word Error Rate using industry-standard jiwer library when available.
    Falls back to basic implementation if jiwer is not installed.
    
    Args:
        reference: Ground truth text
        hypothesis: Predicted/transcribed text
        
    Returns:
        float: Word Error Rate (0.0 = perfect, 1.0 = completely wrong)
    """
    if JIWER_AVAILABLE:
        try:
            # Use jiwer for industry-standard WER calculation
            # This handles proper text normalization, punctuation, etc.
            return jiwer.wer(reference, hypothesis)
        except Exception as e:
            logger.warning(f"jiwer calculation failed, falling back to basic implementation: {e}")
    
    # Fallback to basic implementation (less accurate)
    # Improved to handle basic normalization
    import re
    import string
    
    def normalize_text(text):
        """Basic text normalization."""
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation
        text = text.translate(str.maketrans('', '', string.punctuation))
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    ref_normalized = normalize_text(reference)
    hyp_normalized = normalize_text(hypothesis)
    
    ref_words = ref_normalized.split()
    hyp_words = hyp_normalized.split()
    
    if not ref_words:
        return 1.0 if hyp_words else 0.0
    
    # Levenshtein distance calculation
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    
    wer = dp[m][n] / len(ref_words)
    return float(wer)

def get_audio_duration_seconds(audio_path: str) -> float:
    """
    Get audio duration in seconds with improved precision and reliability.
    
    Strategy (in order of preference):
    1. Try mutagen for most formats (MP3, MP4/M4A, FLAC, OGG, etc.)
    2. Try wave module for WAV files
    3. Size-based estimation as last resort with better assumptions
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        float: Duration in seconds, or 0.0 if unable to determine
    """
    p = Path(audio_path)
    
    if not p.exists():
        logger.warning(f"Audio file does not exist: {audio_path}")
        return 0.0
    
    ext = p.suffix.lower()
    logger.debug(f"Getting duration for {audio_path} (format: {ext})")
    
    # Method 1: Try mutagen first (most reliable for all formats)
    if MutagenFile is not None:
        try:
            mf = MutagenFile(str(p))
            if mf is not None and hasattr(mf, 'info') and hasattr(mf.info, 'length'):
                duration = float(mf.info.length)
                # Sanity check: duration should be positive and reasonable (up to 24 hours)
                if 0 < duration <= 86400:  # 24 hours max
                    logger.debug(f"Mutagen duration: {duration:.3f}s")
                    return duration
                else:
                    logger.warning(f"Mutagen returned unrealistic duration: {duration}s")
        except Exception as e:
            logger.debug(f"Mutagen failed for {audio_path}: {e}")
    
    # Method 2: Try wave module for WAV files
    if ext in ['.wav', '.wave']:
        try:
            with wave.open(str(p), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    duration = frames / float(rate)
                    if 0 < duration <= 86400:  # 24 hours max
                        logger.debug(f"Wave duration: {duration:.3f}s")
                        return duration
                    else:
                        logger.warning(f"Wave returned unrealistic duration: {duration}s")
        except Exception as e:
            logger.debug(f"Wave module failed for {audio_path}: {e}")
    
    # Method 3: Size-based estimation (last resort)
    try:
        file_size = p.stat().st_size
        logger.debug(f"File size: {file_size} bytes")
        
        # Improved size-based estimation with format-specific assumptions
        if ext == '.mp3':
            # Conservative estimate: assume 128kbps (common quality)
            # Higher quality MP3s will give shorter estimates, which is safer than over-estimating
            duration = (file_size * 8) / 128000.0
        elif ext in ['.wav', '.wave']:
            # Assume CD quality: 44.1kHz, 16-bit, stereo
            duration = file_size / (44100 * 2 * 2)  # sample_rate * channels * bytes_per_sample
        elif ext in ['.m4a', '.aac', '.mp4']:
            # Assume 128kbps AAC (common quality)
            duration = (file_size * 8) / 128000.0
        elif ext in ['.flac']:
            # FLAC is lossless, assume ~1MB per minute (rough average)
            duration = file_size / (1024 * 1024 / 60.0)
        elif ext in ['.ogg', '.opus']:
            # Assume 128kbps for OGG Vorbis/Opus
            duration = (file_size * 8) / 128000.0
        else:
            # Generic fallback: assume moderate quality compressed audio
            duration = (file_size * 8) / 128000.0
        
        # Sanity check the size-based estimate
        if 0 < duration <= 86400:  # 24 hours max
            logger.debug(f"Size-based estimate: {duration:.3f}s")
            return duration
        else:
            logger.warning(f"Size-based estimate unrealistic: {duration}s")
            
    except Exception as e:
        logger.warning(f"Size-based estimation failed for {audio_path}: {e}")
    
    logger.warning(f"Unable to determine duration for {audio_path}")
    return 0.0

def calculate_rtf(latency: float, audio_duration: float, metric_name: str = "RTF") -> Optional[float]:
    """
    Calculate Real-Time Factor with validation and bounds checking.
    
    RTF = processing_time / audio_duration
    - RTF < 1.0 means faster than real-time
    - RTF = 1.0 means real-time processing
    - RTF > 1.0 means slower than real-time
    
    Args:
        latency: Processing time in seconds
        audio_duration: Audio duration in seconds
        metric_name: Name for logging (e.g., "TTS RTF", "STT RTF")
        
    Returns:
        float: RTF value, or None if calculation is invalid
    """
    if not audio_duration or audio_duration <= 0:
        logger.debug(f"{metric_name}: Invalid audio duration {audio_duration}")
        return None
        
    if latency < 0:
        logger.warning(f"{metric_name}: Negative latency {latency}")
        return None
    
    rtf = latency / audio_duration
    
    # Validation: RTF should typically be between 0.01 and 100
    # Values outside this range are likely calculation errors
    if rtf < 0.01:
        logger.debug(f"{metric_name}: Unusually low RTF ({rtf:.4f}) - very fast processing")
    elif rtf > 100:
        logger.warning(f"{metric_name}: Unusually high RTF ({rtf:.4f}) - very slow processing or duration error")
        # Don't return None, but log the warning for investigation
    
    return float(rtf)

def get_precision_timer():
    """
    Get a high-precision monotonic timer function.
    Uses time.perf_counter() for better precision than time.perf_counter().
    
    Returns:
        function: Timer function that returns seconds as float
    """
    return time.perf_counter

def validate_confidence(confidence: float, vendor: str = "unknown") -> float:
    """
    Validate and normalize confidence scores.
    
    Args:
        confidence: Raw confidence value
        vendor: Vendor name for logging
        
    Returns:
        float: Validated confidence between 0.0 and 1.0
    """
    if confidence is None:
        logger.debug(f"Confidence is None for {vendor}, defaulting to 0.0")
        return 0.0
    
    try:
        conf = float(confidence)
    except (ValueError, TypeError):
        logger.warning(f"Invalid confidence type for {vendor}: {type(confidence)}")
        return 0.0
    
    # Clamp to valid range first
    if conf < 0.0:
        logger.debug(f"Negative confidence ({conf}) for {vendor}, clamping to 0.0")
        return 0.0
    elif conf > 1.0:
        # Only treat as percentage if it's a reasonable percentage (1.01 to 100.0)
        if conf > 1.01 and conf <= 100.0:
            # Likely percentage, convert to ratio
            logger.debug(f"Confidence {conf} for {vendor} appears to be percentage, converting to ratio")
            return conf / 100.0
        else:
            # Values slightly above 1.0 (like 1.1) are likely just over the limit, clamp to 1.0
            logger.warning(f"Confidence {conf} for {vendor} is too high, clamping to 1.0")
            return 1.0
    
    return conf

# Database helper functions
def get_db_connection():
    """Get SQLite database connection."""
    return sqlite3.connect(DB_PATH)

def dict_factory(cursor, row):
    """Convert SQLite row to dictionary."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# API Endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics (last 7 days)."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        # Basic counts
        cursor.execute("SELECT COUNT(*) as total_runs FROM runs WHERE datetime(started_at) > datetime('now','-7 days')")
        total_runs = cursor.fetchone()["total_runs"]
        cursor.execute("SELECT COUNT(*) as completed_runs FROM runs WHERE status='completed' AND datetime(started_at) > datetime('now','-7 days')")
        completed_runs = cursor.fetchone()["completed_runs"]
        cursor.execute("SELECT COUNT(*) as total_items FROM run_items WHERE datetime(created_at) > datetime('now','-7 days')")
        total_items = cursor.fetchone()["total_items"]
        
        # Avg WER last 7 days
        cursor.execute(
            """
            SELECT AVG(m.value) AS avg_wer
            FROM metrics m
            JOIN run_items ri ON ri.id = m.run_item_id
            WHERE m.metric_name = 'wer'
              AND datetime(ri.created_at) > datetime('now','-7 days')
            """
        )
        wer_row = cursor.fetchone()
        avg_wer = wer_row["avg_wer"] if wer_row and wer_row["avg_wer"] is not None else 0.0
        
        # Prefer E2E latency; fallback to TTS or STT latency
        cursor.execute(
            """
            WITH recent AS (
                SELECT m.value AS v
                FROM metrics m
                JOIN run_items ri ON ri.id = m.run_item_id
                WHERE m.metric_name IN ('e2e_latency') AND datetime(ri.created_at) > datetime('now','-7 days')
                UNION ALL
                SELECT m.value FROM metrics m JOIN run_items ri ON ri.id = m.run_item_id
                WHERE m.metric_name IN ('tts_latency','stt_latency') AND datetime(ri.created_at) > datetime('now','-7 days')
            ) SELECT AVG(v) AS avg_lat FROM recent
            """
        )
        lat_row = cursor.fetchone()
        avg_latency = lat_row["avg_lat"] if lat_row and lat_row["avg_lat"] is not None else 0.0
        
        return {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "total_items": total_items,
            "avg_wer": round(avg_wer, 4),
            "avg_accuracy": round((1 - avg_wer) * 100, 2) if avg_wer > 0 else 95.0,
            "avg_latency": round(avg_latency, 3),
            "success_rate": round((completed_runs / total_runs * 100) if total_runs > 0 else 100.0, 2)
        }
    finally:
        conn.close()

@app.get("/api/dashboard/insights")
async def get_dashboard_insights():
    """Service Mix, Top Vendor Pairings, Vendor Usage (last 7 days)."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        # Fetch items and their metrics for the window
        cursor.execute(
            """
            SELECT ri.*, group_concat(m.metric_name || ':' || m.value, '|') AS metrics_summary
            FROM run_items ri
            LEFT JOIN metrics m ON m.run_item_id = ri.id
            WHERE datetime(ri.created_at) > datetime('now','-7 days')
            GROUP BY ri.id
            """
        )
        items = cursor.fetchall()
        service_mix = {"E2E": 0, "STT": 0, "TTS": 0, "UNKNOWN": 0}
        vendor_usage_tts: Dict[str, int] = {}
        vendor_usage_stt: Dict[str, int] = {}
        pairings: Dict[str, Dict[str, Any]] = {}
        
        for it in items:
            metrics_summary = (it.get("metrics_summary") or "").split("|") if it.get("metrics_summary") else []
            metric_names = set([m.split(":")[0] for m in metrics_summary if ":" in m])
            # Parse metrics_json for vendor pairing where available
            tts_vendor = None
            stt_vendor = None
            try:
                if it.get("metrics_json"):
                    meta = json.loads(it.get("metrics_json"))
                    tts_vendor = meta.get("tts_vendor")
                    stt_vendor = meta.get("stt_vendor")
            except Exception:
                pass
            
            if 'e2e_latency' in metric_names:
                service_mix["E2E"] += 1
                # Count usage by vendors if we know
                if tts_vendor:
                    vendor_usage_tts[tts_vendor] = vendor_usage_tts.get(tts_vendor, 0) + 1
                if stt_vendor:
                    vendor_usage_stt[stt_vendor] = vendor_usage_stt.get(stt_vendor, 0) + 1
                # Pairings with WER
                if tts_vendor and stt_vendor:
                    key = f"{tts_vendor}|{stt_vendor}"
                    if key not in pairings:
                        pairings[key] = {"tts": tts_vendor, "stt": stt_vendor, "wer_sum": 0.0, "count": 0}
                    # Find wer
                    wer_val = None
                    for m in metrics_summary:
                        if m.startswith("wer:"):
                            try:
                                wer_val = float(m.split(":")[1])
                            except Exception:
                                pass
                            break
                    if wer_val is not None:
                        pairings[key]["wer_sum"] += wer_val
                        pairings[key]["count"] += 1
            elif 'stt_latency' in metric_names or 'wer' in metric_names:
                service_mix["STT"] += 1
                vendor_usage_stt[it.get("vendor")] = vendor_usage_stt.get(it.get("vendor"), 0) + 1
            elif 'tts_latency' in metric_names:
                service_mix["TTS"] += 1
                vendor_usage_tts[it.get("vendor")] = vendor_usage_tts.get(it.get("vendor"), 0) + 1
            else:
                service_mix["UNKNOWN"] += 1
        
        top_pairings = []
        for key, p in pairings.items():
            if p["count"] > 0:
                top_pairings.append({
                    "tts_vendor": p["tts"],
                    "stt_vendor": p["stt"],
                    "avg_wer": round(p["wer_sum"] / p["count"], 4),
                    "tests": p["count"],
                })
        # Sort by tests desc
        top_pairings.sort(key=lambda x: (-x["tests"], x["avg_wer"]))
        
        return {
            "service_mix": service_mix,
            "vendor_usage": {"tts": vendor_usage_tts, "stt": vendor_usage_stt},
            "top_vendor_pairings": top_pairings[:5]
        }
    finally:
        conn.close()

@app.get("/api/scripts")
async def api_get_scripts():
    return await get_scripts()

@app.get("/api/dashboard/latency_percentiles")
async def get_latency_percentiles(metric: str = "e2e_latency", days: int = 7):
    """Return p50/p90 latency percentiles for a given metric over the last N days.
    metric: one of e2e_latency|tts_latency|stt_latency
    days: lookback window (default 7)
    """
    if metric not in ("e2e_latency", "tts_latency", "stt_latency"):
        raise HTTPException(status_code=400, detail="Invalid metric. Use e2e_latency|tts_latency|stt_latency")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT m.value
            FROM metrics m
            JOIN run_items ri ON ri.id = m.run_item_id
            WHERE m.metric_name = ?
              AND datetime(ri.created_at) > datetime('now', ?)
            ORDER BY m.value
            """,
            (metric, f"-{int(days)} days"),
        )
        rows = cursor.fetchall()
        # rows are tuples like (value,), flatten and cast to float
        values = []
        for r in rows:
            try:
                values.append(float(r[0]))
            except Exception:
                continue
        n = len(values)
        def percentile(p: float) -> Optional[float]:
            if n == 0:
                return None
            if n == 1:
                return values[0]
            k = p * (n - 1)
            f = int(k)
            c = min(f + 1, n - 1)
            if f == c:
                return values[f]
            d0 = values[f] * (c - k)
            d1 = values[c] * (k - f)
            return d0 + d1
        p50 = percentile(0.5)
        p90 = percentile(0.9)
        return {
            "metric": metric,
            "days": days,
            "count": n,
            "p50": round(p50, 4) if p50 is not None else None,
            "p90": round(p90, 4) if p90 is not None else None,
        }
    finally:
        conn.close()

async def get_scripts():
    """Get all available scripts."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT s.*, COUNT(si.id) as item_count
            FROM scripts s
            LEFT JOIN script_items si ON s.id = si.script_id
            GROUP BY s.id
            """
        )
        scripts = cursor.fetchall()
        for script in scripts:
            cursor.execute("SELECT * FROM script_items WHERE script_id = ?", (script["id"],))
            script["items"] = cursor.fetchall()
        return {"scripts": scripts}
    finally:
        conn.close()

@app.post("/api/runs")
async def create_run(run_data: RunCreate):
    """Create a new test run."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        run_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO runs (id, project_id, mode, vendor_list_json, config_json, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (
                run_id,
                run_data.project_id,
                run_data.mode,
                json.dumps(run_data.vendors),
                json.dumps(run_data.config)
            ),
        )
        # Prepare inputs
        test_inputs = []
        if run_data.text_inputs:
            for text in run_data.text_inputs:
                test_inputs.append({"text": text, "script_item_id": None})
        if run_data.script_ids:
            for script_id in run_data.script_ids:
                cursor.execute("SELECT * FROM script_items WHERE script_id = ?", (script_id,))
                items = cursor.fetchall()
                for item in items:
                    test_inputs.append({"text": item[2], "script_item_id": item[0]})
        if not test_inputs:
            test_inputs = [{"text": "Hello world, this is a test.", "script_item_id": None}]
        # Create run items based on mode
        mode_lower = (run_data.mode or "isolated").lower()
        cfg = run_data.config or {}
        chain = cfg.get("chain") or {}
        # Resolve default pair for chained
        tts_vendor = (chain.get("tts_vendor") or "elevenlabs").lower()
        stt_vendor = (chain.get("stt_vendor") or "deepgram").lower()
        combined_label = f"{tts_vendor}→{stt_vendor}"

        if mode_lower == "chained":
            # One item per input, vendor field is combined label
            for test_input in test_inputs:
                item_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO run_items (id, run_id, script_item_id, vendor, text_input, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        item_id,
                        run_id,
                        test_input["script_item_id"],
                        combined_label,
                        test_input["text"],
                    ),
                )
            # Store combined label in the run vendors list for clarity
            cursor.execute(
                "UPDATE runs SET vendor_list_json = ? WHERE id = ?",
                (json.dumps([combined_label]), run_id),
            )
        else:
            # Isolated mode: one item per vendor per input
            for vendor in run_data.vendors:
                for test_input in test_inputs:
                    item_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO run_items (id, run_id, script_item_id, vendor, text_input, status)
                        VALUES (?, ?, ?, ?, ?, 'pending')
                        """,
                        (
                            item_id,
                            run_id,
                            test_input["script_item_id"],
                            vendor,
                            test_input["text"],
                        ),
                    )
        conn.commit()
        asyncio.create_task(process_run(run_id))
        return {"run_id": run_id, "status": "created", "message": "Run created and processing started"}
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating run: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create run: {str(e)}")
    finally:
        conn.close()

async def process_run(run_id: str):
    """Process a test run asynchronously."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))
        conn.commit()
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()
        mode = run[2]
        cursor.execute("SELECT * FROM run_items WHERE run_id = ? ORDER BY created_at", (run_id,))
        run_items = cursor.fetchall()
        for item in run_items:
            item_id = item[0]
            vendor = item[3]
            text_input = item[4]
            try:
                cursor.execute("UPDATE run_items SET status = 'running' WHERE id = ?", (item_id,))
                conn.commit()
                if mode == "isolated":
                    await process_isolated_mode(item_id, vendor, text_input, conn)
                elif mode == "chained":
                    await process_chained_mode(item_id, vendor, text_input, conn)
                cursor.execute("UPDATE run_items SET status = 'completed' WHERE id = ?", (item_id,))
                conn.commit()
            except Exception as e:
                logger.error(f"Error processing run item {item_id}: {e}")
                cursor.execute("UPDATE run_items SET status = 'failed' WHERE id = ?", (item_id,))
                conn.commit()
        cursor.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
        conn.commit()
    except Exception as e:
        logger.error(f"Error processing run {run_id}: {e}")
        cursor.execute("UPDATE runs SET status = 'failed' WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()

def _get_run_config_for_item(conn, item_id: str) -> Dict[str, Any]:
    try:
        c = conn.cursor()
        c.execute("SELECT run_id FROM run_items WHERE id = ?", (item_id,))
        row = c.fetchone()
        if not row:
            return {}
        run_id = row[0]
        c.execute("SELECT config_json FROM runs WHERE id = ?", (run_id,))
        r = c.fetchone()
        if r and r[0]:
            try:
                return json.loads(r[0]) or {}
            except Exception:
                return {}
        return {}
    except Exception:
        return {}

async def process_isolated_mode(item_id: str, vendor: str, text_input: str, conn):
    """Process isolated mode testing."""
    cursor = conn.cursor()
    cfg = _get_run_config_for_item(conn, item_id)
    service = (cfg.get("service") or ("tts" if vendor in ["elevenlabs", "aws"] else "stt")).lower()

    # Helper: choose model per vendor/service
    def pick_models(vendor_name: str, svc: str) -> Dict[str, Any]:
        models = (cfg.get("models") or {}).get(vendor_name, {})
        if vendor_name == "elevenlabs" and svc == "tts":
            return {"model_id": models.get("tts_model") or "eleven_flash_v2_5", "voice": models.get("voice_id") or "21m00Tcm4TlvDq8ikWAM"}
        if vendor_name == "elevenlabs" and svc == "stt":
            return {"model_id": models.get("stt_model") or "scribe_v1"}
        if vendor_name == "deepgram" and svc == "stt":
            return {"model": models.get("stt_model") or "nova-3"}
        if vendor_name == "deepgram" and svc == "tts":
            # Support both new schema (model+voice) and legacy alias like 'aura-2-thalia-en'
            tts_model = models.get("tts_model") or "aura-2"
            voice = models.get("voice") or "thalia"
            # If legacy alias provided in tts_model, extract voice
            try:
                alias = str(tts_model)
                if alias.startswith("aura-2-") and "-" in alias[7:]:
                    parts = alias.split("-")
                    if len(parts) >= 3:
                        tts_model = "aura-2"
                        voice = parts[2] if parts[1] == "2" else parts[1]
            except Exception:
                pass
            return {"model": tts_model, "voice": voice}
        return {}

    if service == "tts":
        # TTS testing only, but assess using default STT (Deepgram nova-3)
        adapter = VENDOR_ADAPTERS[vendor]["tts"]
        tts_params = pick_models(vendor, "tts")
        tts_result = await adapter.synthesize(text_input, **tts_params)
        if tts_result.get("status") == "success":
            audio_path = tts_result["audio_path"]
            tts_meta = tts_result.get("metadata", {})
            metrics_meta = {
                "service_type": "tts",
                "vendor": vendor,
                "tts_vendor": vendor,
                "tts_model": tts_meta.get("model"),
                "voice_id": tts_meta.get("voice_id")
            }
            cursor.execute(
                "UPDATE run_items SET audio_path = ?, metrics_json = ? WHERE id = ?",
                (audio_path, json.dumps(metrics_meta), item_id),
            )
            duration = get_audio_duration_seconds(audio_path)
            # If duration parser failed but file exists, fall back to a rough estimate using file size and codec hints
            if not duration or duration <= 0:
                try:
                    sz = os.path.getsize(audio_path)
                    # rough fallback: assume ~32kbps for mp3 if container suggests mp3; else assume PCM 24kHz mono 16-bit
                    if str(audio_path).endswith('.mp3'):
                        duration = max(duration or 0.0, (sz * 8) / (32000.0))
                    else:
                        duration = max(duration or 0.0, sz / (24000 * 2))
                except Exception:
                    pass
            tts_latency = float(tts_result.get("latency") or 0.0)
            # Use the new RTF calculation helper with validation
            tts_rtf = calculate_rtf(tts_latency, duration, "TTS RTF")
            metrics = [
                {"name": "tts_latency", "value": tts_latency, "unit": "seconds"},
                {"name": "audio_duration", "value": duration, "unit": "seconds"},
            ]
            if tts_rtf is not None:
                metrics.append({"name": "tts_rtf", "value": tts_rtf, "unit": "x"})
            # Evaluate via Deepgram STT (default nova-3) for WER/accuracy/confidence
            dg_params = pick_models("deepgram", "stt")
            stt_adapter = VENDOR_ADAPTERS["deepgram"]["stt"]
            # Enable formatting and punctuation for better WER accuracy
            stt_result = await stt_adapter.transcribe(
                audio_path,
                **dg_params,
                smart_format=True,
                punctuate=True,
                language="en-US",
            )
            if stt_result.get("status") == "success":
                wer = calculate_wer(text_input, stt_result["transcript"].strip())
                metrics.extend([
                    {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
                    {"name": "accuracy", "value": (1 - wer) * 100, "unit": "percent"},
                    {"name": "confidence", "value": stt_result.get("confidence", 0.0), "unit": "ratio"}
                ])
            for metric in metrics:
                metric_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        metric_id, item_id, metric["name"], metric["value"], metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")
                    ),
                )
            artifact_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO artifacts (id, run_item_id, type, file_path)
                VALUES (?, ?, 'audio', ?)
                """,
                (artifact_id, item_id, audio_path),
            )
            # Save STT evaluation transcript as a file artifact as well
            transcript_text = stt_result.get("transcript")
            if transcript_text:
                try:
                    t_filename = f"transcript_{item_id}.txt"
                    t_path = f"storage/transcripts/{t_filename}"
                    with open(t_path, "w", encoding="utf-8") as tf:
                        tf.write(transcript_text)
                    t_artifact_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO artifacts (id, run_item_id, type, file_path)
                        VALUES (?, ?, 'transcript', ?)
                        """,
                        (t_artifact_id, item_id, t_path),
                    )
                except Exception as e:
                    logger.error(f"Failed to save transcript artifact for {item_id}: {e}")
    else:
        # STT testing: synthesize using ElevenLabs by default (configurable later), then transcribe with selected vendor
        tts_adapter = VENDOR_ADAPTERS["elevenlabs"]["tts"]
        el_params = pick_models("elevenlabs", "tts")
        tts_result = await tts_adapter.synthesize(text_input, **el_params)
        if tts_result.get("status") == "success":
            audio_path = tts_result["audio_path"]
            stt_adapter = VENDOR_ADAPTERS[vendor]["stt"]
            stt_params = pick_models(vendor, "stt")
            stt_result = await stt_adapter.transcribe(audio_path, **stt_params)
            if stt_result.get("status") == "success":
                wer = calculate_wer(text_input, stt_result["transcript"]) 
                duration = get_audio_duration_seconds(audio_path)
                stt_latency = float(stt_result.get("latency") or 0.0)
                # Use the new RTF calculation helper with validation
                stt_rtf = calculate_rtf(stt_latency, duration, "STT RTF")
                # Merge metadata
                existing_meta = {}
                try:
                    cursor.execute("SELECT metrics_json FROM run_items WHERE id = ?", (item_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        existing_meta = json.loads(row[0])
                except Exception:
                    existing_meta = {}
                stt_meta = stt_result.get("metadata", {})
                merged_meta = {**existing_meta, **{
                    "service_type": "stt",
                    "vendor": vendor,
                    "stt_vendor": vendor,
                    "stt_model": stt_meta.get("model"),
                    "language": stt_meta.get("language")
                }}
                cursor.execute(
                    "UPDATE run_items SET transcript = ?, audio_path = ?, metrics_json = ? WHERE id = ?",
                    (stt_result["transcript"], audio_path, json.dumps(merged_meta), item_id),
                )
                metrics = [
                    {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
                    {"name": "accuracy", "value": (1 - wer) * 100, "unit": "percent"},
                    {"name": "confidence", "value": stt_result.get("confidence", 0.0), "unit": "ratio"},
                    {"name": "stt_latency", "value": stt_latency, "unit": "seconds"},
                    {"name": "audio_duration", "value": duration, "unit": "seconds"},
                ]
                if stt_rtf is not None:
                    metrics.append({"name": "stt_rtf", "value": stt_rtf, "unit": "x"})
                for metric in metrics:
                    metric_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            metric_id,
                            item_id,
                            metric["name"],
                            metric["value"],
                            metric.get("unit"),
                            metric.get("threshold"),
                            metric.get("pass_fail"),
                        ),
                    )
                # Save transcript as a file artifact for STT isolated runs
                try:
                    t_filename = f"transcript_{item_id}.txt"
                    t_path = f"storage/transcripts/{t_filename}"
                    with open(t_path, "w", encoding="utf-8") as tf:
                        tf.write(stt_result.get("transcript", ""))
                    t_artifact_id = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO artifacts (id, run_item_id, type, file_path)
                        VALUES (?, ?, 'transcript', ?)
                        """,
                        (t_artifact_id, item_id, t_path),
                    )
                except Exception as e:
                    logger.error(f"Failed to save transcript artifact for {item_id}: {e}")
    conn.commit()

async def process_chained_mode(item_id: str, vendor: str, text_input: str, conn):
    cfg = _get_run_config_for_item(conn, item_id)
    # resolve pairing: cfg.chain could contain tts_vendor, stt_vendor, models
    chain = cfg.get("chain") or {}
    tts_vendor = (chain.get("tts_vendor") or vendor) if vendor in VENDOR_ADAPTERS else (chain.get("tts_vendor") or "elevenlabs")
    stt_vendor = chain.get("stt_vendor") or (vendor if vendor in VENDOR_ADAPTERS else "deepgram")

    def pick_models(vendor_name: str, svc: str) -> Dict[str, Any]:
        models = (cfg.get("models") or {}).get(vendor_name, {})
        if vendor_name == "elevenlabs" and svc == "tts":
            return {"model_id": models.get("tts_model") or "eleven_flash_v2_5", "voice": models.get("voice_id") or "21m00Tcm4TlvDq8ikWAM"}
        if vendor_name == "elevenlabs" and svc == "stt":
            return {"model_id": models.get("stt_model") or "scribe_v1"}
        if vendor_name == "deepgram" and svc == "stt":
            return {"model": models.get("stt_model") or "nova-3"}
        if vendor_name == "deepgram" and svc == "tts":
            # Support both new schema (model+voice) and legacy alias like 'aura-2-thalia-en'
            tts_model = models.get("tts_model") or "aura-2"
            voice = models.get("voice") or "thalia"
            # If legacy alias provided in tts_model, extract voice
            try:
                alias = str(tts_model)
                if alias.startswith("aura-2-") and "-" in alias[7:]:
                    parts = alias.split("-")
                    if len(parts) >= 3:
                        tts_model = "aura-2"
                        voice = parts[2] if parts[1] == "2" else parts[1]
            except Exception:
                pass
            return {"model": tts_model, "voice": voice}
        return {}

    # Step 1: TTS
    tts_adapter = VENDOR_ADAPTERS[tts_vendor]["tts"]
    tts_params = pick_models(tts_vendor, "tts")
    tts_result = await tts_adapter.synthesize(text_input, **tts_params)
    if tts_result.get("status") != "success":
        return
    audio_path = tts_result["audio_path"]

    # Step 2: STT
    stt_adapter = VENDOR_ADAPTERS[stt_vendor]["stt"]
    stt_params = pick_models(stt_vendor, "stt")
    stt_result = await stt_adapter.transcribe(audio_path, **stt_params)
    if stt_result.get("status") != "success":
        return

    # Metrics and storage
    wer = calculate_wer(text_input, stt_result["transcript"])
    tts_latency = float(tts_result.get("latency") or 0.0)
    stt_latency = float(stt_result.get("latency") or 0.0)
    total_latency = tts_latency + stt_latency
    duration = get_audio_duration_seconds(audio_path)
    # Use the new RTF calculation helpers with validation
    tts_rtf = calculate_rtf(tts_latency, duration, "TTS RTF (Chained)")
    stt_rtf = calculate_rtf(stt_latency, duration, "STT RTF (Chained)")
    
    # Store results with correct vendor information
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE run_items SET transcript = ?, audio_path = ?, metrics_json = ? WHERE id = ?",
        (
            stt_result["transcript"],
            audio_path,
            json.dumps({
                "service_type": "e2e",
                "tts_vendor": tts_vendor,
                "stt_vendor": stt_vendor,
                "tts_model": (tts_result.get("metadata") or {}).get("model"),
                "stt_model": (stt_result.get("metadata") or {}).get("model"),
                "voice_id": (tts_result.get("metadata") or {}).get("voice_id"),
                "language": (stt_result.get("metadata") or {}).get("language")
            }),
            item_id,
        ),
    )
    # Save transcript to a file artifact as well for E2E runs
    try:
        t_filename = f"transcript_{item_id}.txt"
        t_path = f"storage/transcripts/{t_filename}"
        with open(t_path, "w", encoding="utf-8") as tf:
            tf.write(stt_result.get("transcript", ""))
        t_artifact_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO artifacts (id, run_item_id, type, file_path)
            VALUES (?, ?, 'transcript', ?)
            """,
            (t_artifact_id, item_id, t_path),
        )
    except Exception as e:
        logger.error(f"Failed to save transcript artifact for {item_id}: {e}")
    metrics = [
        {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
        {"name": "e2e_latency", "value": total_latency, "unit": "seconds"},
        {"name": "tts_latency", "value": tts_latency, "unit": "seconds"},
        {"name": "stt_latency", "value": stt_latency, "unit": "seconds"},
        {"name": "confidence", "value": stt_result.get("confidence", 0.0), "unit": "ratio"},
        {"name": "audio_duration", "value": duration, "unit": "seconds"},
    ]
    if tts_rtf is not None:
        metrics.append({"name": "tts_rtf", "value": tts_rtf, "unit": "x"})
    if stt_rtf is not None:
        metrics.append({"name": "stt_rtf", "value": stt_rtf, "unit": "x"})
    for metric in metrics:
        metric_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metric_id,
                item_id,
                metric["name"],
                metric["value"],
                metric.get("unit"),
                metric.get("threshold"),
                metric.get("pass_fail"),
            ),
        )
    conn.commit()

@app.get("/api/runs")
async def get_runs():
    """Get all runs with their items and metrics."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT r.*, p.name as project_name
            FROM runs r
            LEFT JOIN projects p ON r.project_id = p.id
            ORDER BY r.started_at DESC
            LIMIT 50
            """
        )
        runs = cursor.fetchall()
        for run in runs:
            cursor.execute(
                """
                SELECT ri.*, 
                       GROUP_CONCAT(m.metric_name || ':' || m.value, '|') as metrics_summary
                FROM run_items ri
                LEFT JOIN metrics m ON ri.id = m.run_item_id
                WHERE ri.run_id = ?
                GROUP BY ri.id
                """,
                (run["id"],),
            )
            run["items"] = cursor.fetchall()
            try:
                run["vendors"] = json.loads(run["vendor_list_json"])
            except Exception:
                run["vendors"] = []
        return {"runs": runs}
    finally:
        conn.close()

@app.get("/api/runs/{run_id}")
async def get_run_details(run_id: str):
    """Get detailed run information."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        cursor.execute(
            """
            SELECT ri.*
            FROM run_items ri
            WHERE ri.run_id = ?
            ORDER BY ri.created_at
            """,
            (run_id,),
        )
        items = cursor.fetchall()
        for item in items:
            cursor.execute("""SELECT * FROM metrics WHERE run_item_id = ?""", (item["id"],))
            item["metrics"] = cursor.fetchall()
            cursor.execute("""SELECT * FROM artifacts WHERE run_item_id = ?""", (item["id"],))
            item["artifacts"] = cursor.fetchall()
        run["items"] = items
        try:
            run["vendors"] = json.loads(run["vendor_list_json"])
            run["config"] = json.loads(run["config_json"] or "{}")
        except Exception:
            run["vendors"] = []
            run["config"] = {}
        return {"run": run}
    finally:
        conn.close()

@app.post("/api/runs/quick")
async def create_quick_run(
    text: str = Form(...),
    vendors: str = Form(...),
    mode: str = Form("isolated"),
    config: Optional[str] = Form(None),
):
    """Create a quick test run with single text input."""
    try:
        vendor_list = [v.strip() for v in vendors.split(",")]
        cfg: Dict[str, Any] = {}
        if config:
            try:
                cfg = json.loads(config)
            except Exception:
                cfg = {}
        run_data = RunCreate(mode=mode, vendors=vendor_list, text_inputs=[text], config=cfg)
        result = await create_run(run_data)
        return result
    except Exception as e:
        logger.error(f"Error creating quick run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/export")
async def export_results(payload: Dict[str, Any]):
    """Export selected results as CSV or PDF. Body: {format: 'csv'|'pdf', run_item_ids?: [..], all?: bool}"""
    fmt = (payload or {}).get("format", "csv").lower()
    run_item_ids: Optional[List[str]] = (payload or {}).get("run_item_ids")
    export_all: bool = bool((payload or {}).get("all"))
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        if export_all or not run_item_ids:
            cursor.execute(
                """
                SELECT ri.*, r.mode, r.started_at,
                       GROUP_CONCAT(m.metric_name || ':' || m.value, '|') as metrics_summary
                FROM run_items ri
                JOIN runs r ON r.id = ri.run_id
                LEFT JOIN metrics m ON m.run_item_id = ri.id
                WHERE datetime(ri.created_at) > datetime('now','-30 days')
                GROUP BY ri.id
                ORDER BY ri.created_at DESC
                """
            )
        else:
            qmarks = ",".join(["?"] * len(run_item_ids))
            cursor.execute(
                f"""
                SELECT ri.*, r.mode, r.started_at,
                       GROUP_CONCAT(m.metric_name || ':' || m.value, '|') as metrics_summary
                FROM run_items ri
                JOIN runs r ON r.id = ri.run_id
                LEFT JOIN metrics m ON m.run_item_id = ri.id
                WHERE ri.id IN ({qmarks})
                GROUP BY ri.id
                ORDER BY ri.created_at DESC
                """,
                run_item_ids,
            )
        rows = cursor.fetchall()
        # Build normalized rows
        norm = []
        for row in rows:
            metrics_map = {}
            if row.get("metrics_summary"):
                for kv in row["metrics_summary"].split("|"):
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        try:
                            metrics_map[k] = float(v)
                        except Exception:
                            metrics_map[k] = v
            service = "UNKNOWN"
            if "e2e_latency" in metrics_map:
                service = "E2E"
            elif ("stt_latency" in metrics_map) or ("wer" in metrics_map):
                service = "STT"
            elif "tts_latency" in metrics_map:
                service = "TTS"
            norm.append({
                "run_id": row.get("run_id"),
                "run_item_id": row.get("id"),
                "started_at": row.get("started_at"),
                "mode": row.get("mode"),
                "vendor": row.get("vendor"),
                "service": service,
                "text_input": row.get("text_input"),
                "transcript": row.get("transcript"),
                "wer": metrics_map.get("wer"),
                "accuracy": metrics_map.get("accuracy"),
                "confidence": metrics_map.get("confidence"),
                "e2e_latency": metrics_map.get("e2e_latency"),
                "tts_latency": metrics_map.get("tts_latency"),
                "stt_latency": metrics_map.get("stt_latency"),
                "audio_duration": metrics_map.get("audio_duration"),
                "tts_rtf": metrics_map.get("tts_rtf"),
                "stt_rtf": metrics_map.get("stt_rtf"),
                "audio_path": row.get("audio_path"),
            })
        if fmt == "csv":
            output = io.StringIO()
            fieldnames = [
                "run_id",
                "run_item_id",
                "started_at",
                "mode",
                "vendor",
                "service",
                "text_input",
                "transcript",
                "wer",
                "accuracy",
                "confidence",
                "e2e_latency",
                "tts_latency",
                "stt_latency",
                "audio_duration",
                "tts_rtf",
                "stt_rtf",
                "audio_path",
            ]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for r in norm:
                writer.writerow(r)
            csv_bytes = output.getvalue().encode("utf-8")
            headers = {"Content-Disposition": f"attachment; filename=benchmark_export_{int(time.perf_counter())}.csv"}
            return Response(content=csv_bytes, media_type="text/csv", headers=headers)
        elif fmt == "pdf":
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"PDF export requires reportlab: {e}")
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            x_margin = 0.5 * inch
            y = height - 0.75 * inch
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x_margin, y, "TTS/STT Benchmark Export")
            y -= 0.3 * inch
            c.setFont("Helvetica", 9)
            for r in norm:
                line = f"{r['started_at']} | {r['mode']} | {r['vendor']} | {r['service']} | WER: {r.get('wer')} | E2E: {r.get('e2e_latency')}s | TTS: {r.get('tts_latency')}s | STT: {r.get('stt_latency')}s"
                for chunk in [line[i:i+110] for i in range(0, len(line), 110)]:
                    c.drawString(x_margin, y, chunk)
                    y -= 12
                    if y < 0.75 * inch:
                        c.showPage()
                        c.setFont("Helvetica", 9)
                        y = height - 0.75 * inch
                # Next item spacing
                y -= 6
                if y < 0.75 * inch:
                    c.showPage()
                    c.setFont("Helvetica", 9)
                    y = height - 0.75 * inch
            c.showPage()
            c.save()
            pdf_bytes = buffer.getvalue()
            headers = {"Content-Disposition": f"attachment; filename=benchmark_export_{int(time.perf_counter())}.pdf"}
            return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
        else:
            raise HTTPException(status_code=400, detail="Invalid export format. Use 'csv' or 'pdf'.")
    finally:
        conn.close()

@app.get("/api/audio/{filename}")
async def serve_audio(filename: str):
    """Serve audio files."""
    audio_path = f"storage/audio/{filename}"
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    # rudimentary content type detection
    mime = "audio/mpeg"
    if filename.lower().endswith(".wav"):
        mime = "audio/wav"
    with open(audio_path, "rb") as f:
        content = f.read()
    return Response(content=content, media_type=mime)

@app.get("/api/transcript/{filename}")
async def serve_transcript(filename: str):
    """Serve transcript text files saved as artifacts."""
    t_path = f"storage/transcripts/{filename}"
    if not os.path.exists(t_path):
        raise HTTPException(status_code=404, detail="Transcript file not found")
    with open(t_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/plain; charset=utf-8")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)