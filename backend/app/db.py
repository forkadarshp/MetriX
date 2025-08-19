import sqlite3
from typing import Any, Dict

from .config import DB_PATH, logger


def init_database() -> None:
    """Initialize SQLite database with required tables and seed data."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.executescript(
        """
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

        CREATE TABLE IF NOT EXISTS subjective_metrics (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            service_type TEXT NOT NULL CHECK (service_type IN ('tts', 'stt')),
            scale_min INTEGER DEFAULT 1,
            scale_max INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_ratings (
            id TEXT PRIMARY KEY,
            run_item_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            subjective_metric_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_item_id) REFERENCES run_items (id),
            FOREIGN KEY (subjective_metric_id) REFERENCES subjective_metrics (id),
            UNIQUE(run_item_id, user_name, subjective_metric_id)
        );

        INSERT OR IGNORE INTO users (id, name, role) VALUES ('default_user', 'Default User', 'admin');
        INSERT OR IGNORE INTO projects (id, name, description) VALUES ('default_project', 'Default Project', 'Default benchmarking project');

        INSERT OR IGNORE INTO scripts (id, name, description, tags) VALUES 
        ('banking_script', 'Banking Script', 'Banking domain test phrases', 'banking,finance'),
        ('general_script', 'General Script', 'General purpose test phrases', 'general');

        INSERT OR IGNORE INTO script_items (id, script_id, text, lang, tags) VALUES 
        ('item_1', 'banking_script', 'Welcome to our banking services. How can I help you today?', 'en-US', 'greeting'),
        ('item_2', 'banking_script', 'Your account balance is one thousand two hundred and fifty dollars.', 'en-US', 'numbers'),
        ('item_3', 'banking_script', 'Please verify your identity by providing your social security number.', 'en-US', 'security'),
        ('item_4', 'general_script', 'The quick brown fox jumps over the lazy dog.', 'en-US', 'pangram'),
        ('item_5', 'general_script', 'Hello world, this is a test of the speech recognition system.', 'en-US', 'test');

        INSERT OR IGNORE INTO subjective_metrics (id, name, description, service_type, scale_min, scale_max) VALUES 
        ('tts_naturalness', 'Speech Naturalness', 'How natural and human-like does the speech sound?', 'tts', 1, 5),
        ('tts_disfluency', 'Disfluency Handling', 'How well does the system handle pauses, hesitations, and speech disfluencies?', 'tts', 1, 5),
        ('tts_context', 'Context Awareness', 'How well does the speech reflect the context and meaning of the text?', 'tts', 1, 5),
        ('tts_prosody', 'Prosody Accuracy', 'How accurate are the rhythm, stress, and intonation patterns?', 'tts', 1, 5);

        INSERT OR IGNORE INTO subjective_metrics (id, name, description, service_type, scale_min, scale_max) VALUES 
        ('stt_disfluency', 'Disfluency Recognition', 'How well does the system recognize and handle speech disfluencies?', 'stt', 1, 5),
        ('stt_language_switch', 'Language Switching Accuracy', 'How accurately does the system handle language switches within speech?', 'stt', 1, 5);
        """
    )

    conn.commit()
    conn.close()


def get_db_connection() -> sqlite3.Connection:
    """Get SQLite database connection."""
    return sqlite3.connect(str(DB_PATH))


def dict_factory(cursor, row) -> Dict[str, Any]:
    """Convert SQLite row to dictionary."""
    d: Dict[str, Any] = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


