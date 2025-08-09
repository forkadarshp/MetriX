from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Form
from fastapi.responses import Response
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

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY", "dummy_eleven_key")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "dummy_deepgram_key")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY", "dummy_aws_key")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY", "dummy_aws_secret")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize FastAPI app
app = FastAPI(title="TTS/STT Benchmarking Dashboard", version="1.0.0")

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
    
    async def synthesize(self, text: str, voice: str = "21m00Tcm4TlvDq8ikWAM", model_id: str = "eleven_multilingual_v2", **params) -> Dict[str, Any]:
        """Synthesize text using ElevenLabs TTS."""
        start_time = time.time()
        
        if self.is_dummy:
            # Dummy implementation
            await asyncio.sleep(0.5)  # Simulate API delay
            audio_filename = f"elevenlabs_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            
            # Create a dummy audio file
            with open(audio_path, "wb") as f:
                f.write(b"dummy_audio_data_elevenlabs")
            
            latency = time.time() - start_time
            return {
                "audio_path": audio_path,
                "vendor": "elevenlabs",
                "voice": voice,
                "latency": latency,
                "status": "success",
                "metadata": {"model": model_id, "voice_id": voice}
            }
        else:
            # Real implementation
            try:
                from elevenlabs import ElevenLabs
                
                client = ElevenLabs(api_key=self.api_key)
                
                # Generate audio
                audio_generator = client.text_to_speech.convert(
                    text=text,
                    voice_id=voice,
                    model_id=model_id
                )
                
                # Save audio file
                audio_filename = f"elevenlabs_{uuid.uuid4().hex}.mp3"
                audio_path = f"storage/audio/{audio_filename}"
                
                with open(audio_path, "wb") as f:
                    for chunk in audio_generator:
                        f.write(chunk)
                
                latency = time.time() - start_time
                return {
                    "audio_path": audio_path,
                    "vendor": "elevenlabs",
                    "voice": voice,
                    "latency": latency,
                    "status": "success",
                    "metadata": {"model": model_id, "voice_id": voice}
                }
            except Exception as e:
                logger.error(f"ElevenLabs synthesis error: {e}")
                return {"status": "error", "error": str(e), "latency": time.time() - start_time}

    async def transcribe(self, audio_path: str, model_id: str = "scribe_v1", **params) -> Dict[str, Any]:
        """Transcribe audio using ElevenLabs STT (Scribe)."""
        start_time = time.time()
        if self.is_dummy:
            await asyncio.sleep(0.3)
            return {
                "transcript": "Dummy transcription from ElevenLabs Scribe.",
                "confidence": 0.92,
                "vendor": "elevenlabs",
                "latency": time.time() - start_time,
                "status": "success",
                "metadata": {"model": model_id}
            }
        try:
            from elevenlabs import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)
            with open(audio_path, 'rb') as audio_file:
                result = client.speech_to_text.convert(
                    audio=audio_file,
                    model_id=model_id,
                )
            transcript = result.get('text') or result.get('transcript') or ''
            confidence = result.get('confidence', 0.0)
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "elevenlabs",
                "latency": time.time() - start_time,
                "status": "success",
                "metadata": {"model": model_id}
            }
        except Exception as e:
            logger.error(f"ElevenLabs transcription error: {e}")
            return {"status": "error", "error": str(e), "latency": time.time() - start_time}

class DeepgramAdapter(VendorAdapter):
    """Deepgram STT/TTS adapter."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.is_dummy = api_key == "dummy_deepgram_key"
    
    async def transcribe(self, audio_path: str, model: str = "nova-3", **params) -> Dict[str, Any]:
        """Transcribe audio using Deepgram STT."""
        start_time = time.time()
        
        if self.is_dummy:
            # Dummy implementation - extract text from filename or use sample
            await asyncio.sleep(0.3)  # Simulate API delay
            
            # For demo purposes, return a sample transcript
            dummy_transcripts = [
                "Welcome to our banking services. How can I help you today?",
                "Your account balance is one thousand two hundred fifty dollars.",
                "The quick brown fox jumps over the lazy dog.",
                "Hello world, this is a test of the speech recognition system."
            ]
            
            transcript = dummy_transcripts[hash(audio_path) % len(dummy_transcripts)]
            confidence = 0.85 + (hash(audio_path) % 15) / 100  # Random confidence between 0.85-1.0
            
            latency = time.time() - start_time
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "deepgram",
                "latency": latency,
                "status": "success",
                "metadata": {"model": model, "language": "en-US"}
            }
        else:
            # Real implementation
            try:
                from deepgram import DeepgramClient, PrerecordedOptions, FileSource
                
                client = DeepgramClient(self.api_key)
                
                options = PrerecordedOptions(
                    model=model,
                    smart_format=True,
                    punctuate=True,
                    language="en-US"
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
                
                latency = time.time() - start_time
                return {
                    "transcript": transcript,
                    "confidence": confidence,
                    "vendor": "deepgram",
                    "latency": latency,
                    "status": "success",
                    "metadata": {"model": model, "language": "en-US"}
                }
            except Exception as e:
                logger.error(f"Deepgram transcription error: {e}")
                return {"status": "error", "error": str(e), "latency": time.time() - start_time}

    async def synthesize(self, text: str, model: str = "aura-2-thalia-en", encoding: str = "linear16", sample_rate: int = 24000, **params) -> Dict[str, Any]:
        """Synthesize speech using Deepgram Speak API (Aura 2)."""
        start_time = time.time()
        ttfb = None
        if self.is_dummy:
            await asyncio.sleep(0.4)
            audio_filename = f"deepgram_tts_{uuid.uuid4().hex}.wav"
            audio_path = f"storage/audio/{audio_filename}"
            with open(audio_path, "wb") as f:
                f.write(b"dummy_deepgram_tts_audio")
            return {
                "audio_path": audio_path,
                "vendor": "deepgram",
                "latency": time.time() - start_time,
                "status": "success",
                "metadata": {"model": model, "encoding": encoding, "sample_rate": sample_rate}
            }
        try:
            url = "https://api.deepgram.com/v1/speak"
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json"
            }
            params = {
                "model": model,
                "encoding": encoding,
                "sample_rate": str(sample_rate)
            }
            payload = {"text": text}
            audio_filename = f"deepgram_tts_{uuid.uuid4().hex}.wav"
            audio_path = f"storage/audio/{audio_filename}"
            file_size = 0
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, params=params, json=payload, timeout=60.0) as resp:
                    if resp.status_code != 200:
                        error_text = await resp.aread()
                        return {"status": "error", "error": f"HTTP {resp.status_code}: {error_text.decode()}", "latency": time.time() - start_time}
                    async with aiofiles.open(audio_path, 'wb') as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024):
                            if ttfb is None:
                                ttfb = time.time() - start_time
                            await f.write(chunk)
                            file_size += len(chunk)
            latency = time.time() - start_time
            return {
                "audio_path": audio_path,
                "vendor": "deepgram",
                "latency": latency,
                "ttfb": ttfb or latency,
                "status": "success",
                "metadata": {"model": model, "encoding": encoding, "sample_rate": sample_rate, "file_size": file_size}
            }
        except Exception as e:
            logger.error(f"Deepgram TTS error: {e}")
            return {"status": "error", "error": str(e), "latency": time.time() - start_time}

class AWSAdapter(VendorAdapter):
    """AWS Polly/Transcribe adapter using dummy implementation."""
    
    def __init__(self, access_key: str, secret_key: str, region: str):
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region
        self.is_dummy = access_key == "dummy_aws_key"
    
    async def synthesize(self, text: str, voice: str = "Joanna", **params) -> Dict[str, Any]:
        """Synthesize text using AWS Polly."""
        start_time = time.time()
        
        if self.is_dummy:
            await asyncio.sleep(0.4)  # Simulate API delay
            audio_filename = f"aws_polly_{uuid.uuid4().hex}.mp3"
            audio_path = f"storage/audio/{audio_filename}"
            
            with open(audio_path, "wb") as f:
                f.write(b"dummy_audio_data_aws_polly")
            
            latency = time.time() - start_time
            return {
                "audio_path": audio_path,
                "vendor": "aws_polly",
                "voice": voice,
                "latency": latency,
                "status": "success",
                "metadata": {"engine": "neural", "voice_id": voice}
            }
        else:
            # Real AWS Polly implementation would go here
            latency = time.time() - start_time
            return {"status": "error", "error": "Real AWS implementation not available", "latency": latency}
    
    async def transcribe(self, audio_path: str, **params) -> Dict[str, Any]:
        """Transcribe audio using AWS Transcribe."""
        start_time = time.time()
        
        if self.is_dummy:
            await asyncio.sleep(0.6)  # Simulate API delay
            
            dummy_transcripts = [
                "Welcome to our banking services how can I help you today",
                "Your account balance is one thousand two hundred fifty dollars",
                "The quick brown fox jumps over the lazy dog",
                "Hello world this is a test of the speech recognition system"
            ]
            
            transcript = dummy_transcripts[hash(audio_path) % len(dummy_transcripts)]
            confidence = 0.80 + (hash(audio_path) % 20) / 100
            
            latency = time.time() - start_time
            return {
                "transcript": transcript,
                "confidence": confidence,
                "vendor": "aws_transcribe",
                "latency": latency,
                "status": "success",
                "metadata": {"job_name": f"job_{uuid.uuid4().hex}", "language": "en-US"}
            }
        else:
            # Real AWS Transcribe implementation would go here
            latency = time.time() - start_time
            return {"status": "error", "error": "Real AWS implementation not available", "latency": latency}

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
    """Calculate Word Error Rate using simple implementation."""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    
    # Simple edit distance calculation
    if not ref_words:
        return 1.0 if hyp_words else 0.0
    
    # Dynamic programming approach for edit distance
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
    
    return dp[m][n] / len(ref_words)

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
    """Get dashboard statistics."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    try:
        # Get basic counts
        cursor.execute("SELECT COUNT(*) as total_runs FROM runs")
        total_runs = cursor.fetchone()["total_runs"]
        
        cursor.execute("SELECT COUNT(*) as completed_runs FROM runs WHERE status = 'completed'")
        completed_runs = cursor.fetchone()["completed_runs"]
        
        cursor.execute("SELECT COUNT(*) as total_items FROM run_items")
        total_items = cursor.fetchone()["total_items"]
        
        # Get average metrics from recent runs
        cursor.execute("""
            SELECT AVG(value) as avg_wer 
            FROM metrics 
            WHERE metric_name = 'wer' 
            AND datetime(metrics.id) > datetime('now', '-7 days')
        """)
        wer_result = cursor.fetchone()
        avg_wer = wer_result["avg_wer"] if wer_result and wer_result["avg_wer"] else 0.0
        
        cursor.execute("""
            SELECT AVG(value) as avg_latency 
            FROM metrics 
            WHERE metric_name = 'latency'
            AND datetime(metrics.id) > datetime('now', '-7 days')
        """)
        latency_result = cursor.fetchone()
        avg_latency = latency_result["avg_latency"] if latency_result and latency_result["avg_latency"] else 0.0
        
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

@app.get("/api/scripts")
async def get_scripts():
    """Get all available scripts."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT s.*, COUNT(si.id) as item_count
            FROM scripts s
            LEFT JOIN script_items si ON s.id = si.script_id
            GROUP BY s.id
        """)
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
        
        # Insert run record
        cursor.execute("""
            INSERT INTO runs (id, project_id, mode, vendor_list_json, config_json, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (
            run_id,
            run_data.project_id,
            run_data.mode,
            json.dumps(run_data.vendors),
            json.dumps(run_data.config)
        ))
        
        # Prepare test inputs
        test_inputs = []
        
        if run_data.text_inputs:
            # Direct text inputs
            for text in run_data.text_inputs:
                test_inputs.append({"text": text, "script_item_id": None})
        
        if run_data.script_ids:
            # Get script items
            for script_id in run_data.script_ids:
                cursor.execute("SELECT * FROM script_items WHERE script_id = ?", (script_id,))
                items = cursor.fetchall()
                for item in items:
                    test_inputs.append({"text": item[2], "script_item_id": item[0]})  # item[2] is text
        
        # If no inputs provided, use default
        if not test_inputs:
            test_inputs = [{"text": "Hello world, this is a test.", "script_item_id": None}]
        
        # Create run items for each vendor and input combination
        for vendor in run_data.vendors:
            for test_input in test_inputs:
                item_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO run_items (id, run_id, script_item_id, vendor, text_input, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                """, (
                    item_id,
                    run_id,
                    test_input["script_item_id"],
                    vendor,
                    test_input["text"]
                ))
        
        conn.commit()
        
        # Start processing run asynchronously
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
        # Update run status to running
        cursor.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))
        conn.commit()
        
        # Get run details
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()
        mode = run[2]  # mode is the 3rd column
        
        # Get all run items
        cursor.execute("SELECT * FROM run_items WHERE run_id = ? ORDER BY created_at", (run_id,))
        run_items = cursor.fetchall()
        
        for item in run_items:
            item_id = item[0]
            vendor = item[3]
            text_input = item[4]
            
            try:
                # Update item status
                cursor.execute("UPDATE run_items SET status = 'running' WHERE id = ?", (item_id,))
                conn.commit()
                
                if mode == "isolated":
                    await process_isolated_mode(item_id, vendor, text_input, conn)
                elif mode == "chained":
                    await process_chained_mode(item_id, vendor, text_input, conn)
                
                # Update item status to completed
                cursor.execute("UPDATE run_items SET status = 'completed' WHERE id = ?", (item_id,))
                conn.commit()
                
            except Exception as e:
                logger.error(f"Error processing run item {item_id}: {e}")
                cursor.execute("UPDATE run_items SET status = 'failed' WHERE id = ?", (item_id,))
                conn.commit()
        
        # Update run status to completed
        cursor.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
        conn.commit()
        
    except Exception as e:
        logger.error(f"Error processing run {run_id}: {e}")
        cursor.execute("UPDATE runs SET status = 'failed' WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()

async def process_isolated_mode(item_id: str, vendor: str, text_input: str, conn):
    """Process isolated mode testing."""
    cursor = conn.cursor()
    
    if vendor in ["elevenlabs", "aws"]:
        # TTS testing
        adapter = VENDOR_ADAPTERS[vendor]["tts"]
        if adapter:
            tts_result = await adapter.synthesize(text_input)
            
            if tts_result["status"] == "success":
                # Store audio path
                cursor.execute(
                    "UPDATE run_items SET audio_path = ? WHERE id = ?",
                    (tts_result["audio_path"], item_id)
                )
                
                # Store TTS metrics
                metrics = [
                    {"name": "latency", "value": tts_result["latency"], "unit": "seconds"},
                    {"name": "audio_duration", "value": len(text_input) * 0.05, "unit": "seconds"},  # Estimate
                ]
                
                for metric in metrics:
                    metric_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO metrics (id, run_item_id, metric_name, value, unit)
                        VALUES (?, ?, ?, ?, ?)
                    """, (metric_id, item_id, metric["name"], metric["value"], metric.get("unit")))
                
                # Store artifact
                artifact_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO artifacts (id, run_item_id, type, file_path)
                    VALUES (?, ?, 'audio', ?)
                """, (artifact_id, item_id, tts_result["audio_path"]))
    
    elif vendor in ["deepgram", "aws"]:
        # STT testing - need audio first
        if vendor == "deepgram":
            # For demo, create TTS first then transcribe
            tts_adapter = VENDOR_ADAPTERS["elevenlabs"]["tts"]
            tts_result = await tts_adapter.synthesize(text_input)
            
            if tts_result["status"] == "success":
                stt_adapter = VENDOR_ADAPTERS[vendor]["stt"]
                stt_result = await stt_adapter.transcribe(tts_result["audio_path"])
                
                if stt_result["status"] == "success":
                    # Calculate WER
                    wer = calculate_wer(text_input, stt_result["transcript"])
                    
                    # Store results
                    cursor.execute(
                        "UPDATE run_items SET transcript = ?, audio_path = ? WHERE id = ?",
                        (stt_result["transcript"], tts_result["audio_path"], item_id)
                    )
                    
                    # Store metrics
                    metrics = [
                        {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.1, "pass_fail": "pass" if wer <= 0.1 else "fail"},
                        {"name": "accuracy", "value": (1 - wer) * 100, "unit": "percent"},
                        {"name": "confidence", "value": stt_result["confidence"], "unit": "ratio"},
                        {"name": "latency", "value": stt_result["latency"], "unit": "seconds"},
                    ]
                    
                    for metric in metrics:
                        metric_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (metric_id, item_id, metric["name"], metric["value"], 
                             metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")))
    
    conn.commit()

async def process_chained_mode(item_id: str, vendor: str, text_input: str, conn):
    """Process chained mode testing (TTS -> STT)."""
    cursor = conn.cursor()
    
    # For chained mode, we need both TTS and STT
    # Use the vendor's TTS if available, otherwise use ElevenLabs
    tts_vendor = vendor if vendor in ["elevenlabs", "aws"] else "elevenlabs"
    stt_vendor = vendor if vendor in ["deepgram", "aws"] else "deepgram"
    
    # Step 1: TTS
    tts_adapter = VENDOR_ADAPTERS[tts_vendor]["tts"]
    tts_result = await tts_adapter.synthesize(text_input)
    
    if tts_result["status"] != "success":
        return
    
    # Step 2: STT
    stt_adapter = VENDOR_ADAPTERS[stt_vendor]["stt"]
    stt_result = await stt_adapter.transcribe(tts_result["audio_path"])
    
    if stt_result["status"] != "success":
        return
    
    # Calculate end-to-end metrics
    wer = calculate_wer(text_input, stt_result["transcript"])
    total_latency = tts_result["latency"] + stt_result["latency"]
    
    # Store results
    cursor.execute(
        "UPDATE run_items SET transcript = ?, audio_path = ? WHERE id = ?",
        (stt_result["transcript"], tts_result["audio_path"], item_id)
    )
    
    # Store metrics
    metrics = [
        {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
        {"name": "e2e_latency", "value": total_latency, "unit": "seconds"},
        {"name": "tts_latency", "value": tts_result["latency"], "unit": "seconds"},
        {"name": "stt_latency", "value": stt_result["latency"], "unit": "seconds"},
        {"name": "confidence", "value": stt_result["confidence"], "unit": "ratio"},
    ]
    
    for metric in metrics:
        metric_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (metric_id, item_id, metric["name"], metric["value"], 
             metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")))
    
    conn.commit()

@app.get("/api/runs")
async def get_runs():
    """Get all runs with their items and metrics."""
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    try:
        # Get runs
        cursor.execute("""
            SELECT r.*, p.name as project_name
            FROM runs r
            LEFT JOIN projects p ON r.project_id = p.id
            ORDER BY r.started_at DESC
            LIMIT 50
        """)
        runs = cursor.fetchall()
        
        for run in runs:
            # Get run items
            cursor.execute("""
                SELECT ri.*, 
                       GROUP_CONCAT(m.metric_name || ':' || m.value, '|') as metrics_summary
                FROM run_items ri
                LEFT JOIN metrics m ON ri.id = m.run_item_id
                WHERE ri.run_id = ?
                GROUP BY ri.id
            """, (run["id"],))
            run["items"] = cursor.fetchall()
            
            # Parse vendor list
            try:
                run["vendors"] = json.loads(run["vendor_list_json"])
            except:
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
        # Get run
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()
        
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get run items with metrics
        cursor.execute("""
            SELECT ri.*
            FROM run_items ri
            WHERE ri.run_id = ?
            ORDER BY ri.created_at
        """, (run_id,))
        items = cursor.fetchall()
        
        for item in items:
            # Get metrics for this item
            cursor.execute("""
                SELECT * FROM metrics WHERE run_item_id = ?
            """, (item["id"],))
            item["metrics"] = cursor.fetchall()
            
            # Get artifacts
            cursor.execute("""
                SELECT * FROM artifacts WHERE run_item_id = ?
            """, (item["id"],))
            item["artifacts"] = cursor.fetchall()
        
        run["items"] = items
        
        # Parse JSON fields
        try:
            run["vendors"] = json.loads(run["vendor_list_json"])
            run["config"] = json.loads(run["config_json"] or "{}")
        except:
            run["vendors"] = []
            run["config"] = {}
        
        return {"run": run}
    finally:
        conn.close()

@app.post("/api/runs/quick")
async def create_quick_run(
    text: str = Form(...),
    vendors: str = Form(...),
    mode: str = Form("isolated")
):
    """Create a quick test run with single text input."""
    try:
        vendor_list = [v.strip() for v in vendors.split(",")]
        
        run_data = RunCreate(
            mode=mode,
            vendors=vendor_list,
            text_inputs=[text]
        )
        
        result = await create_run(run_data)
        return result
        
    except Exception as e:
        logger.error(f"Error creating quick run: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio/{filename}")
async def serve_audio(filename: str):
    """Serve audio files."""
    audio_path = f"storage/audio/{filename}"
    
    if not os.path.exists(audio_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    # Return file content
    with open(audio_path, "rb") as f:
        content = f.read()
    
    return Response(content=content, media_type="audio/mpeg")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)