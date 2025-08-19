"""
TTS/STT Benchmarking Dashboard - Production-Grade Modular Server

This module bootstraps a FastAPI application with modular architecture:
- Configuration and environment setup
- Database initialization
- CORS middleware
- Modular router inclusion
- Uvicorn server startup

The business logic is organized into:
- app/config.py: Environment variables and configuration
- app/db.py: Database initialization and helpers
- app/models.py: Pydantic models
- app/utils.py: Utility functions (WER, RTF, audio duration)
- app/vendors/: Vendor adapters (ElevenLabs, Deepgram, AWS)
- app/services/: Business logic services
- app/routers/: API route handlers
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import modular components
from app.config import CORS_ORIGINS, ensure_directories
from app.db import init_database
from app.routers import dashboard, scripts, runs, metrics, exporter, files, ratings

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

# Ensure required directories exist
ensure_directories()

# Initialize database on startup
init_database()

# Include all API routers
app.include_router(dashboard.router)
app.include_router(scripts.router)
app.include_router(runs.router)
app.include_router(metrics.router)
app.include_router(exporter.router)
app.include_router(files.router)
app.include_router(ratings.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)