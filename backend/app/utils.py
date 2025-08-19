import io
import time
import wave
import string
import logging
import traceback
from pathlib import Path
from typing import Any, Optional

from .config import logger


# Optional libraries
try:
    import jiwer  # type: ignore
    JIWER_AVAILABLE = True
except Exception:
    JIWER_AVAILABLE = False
    logger.warning("jiwer not available - using fallback WER calculation (less accurate)")

try:
    from mutagen import File as MutagenFile  # type: ignore
except Exception:
    MutagenFile = None  # type: ignore


def calculate_wer(reference: str, hypothesis: str) -> float:
    if JIWER_AVAILABLE:
        try:
            # Normalize text ourselves for maximum compatibility across jiwer versions
            import re as _re

            def _normalize_for_wer(text: str) -> str:
                t = text.strip().lower()
                t = _re.sub(r"[-–—_/]", " ", t)
                t = t.translate(str.maketrans('', '', string.punctuation))
                t = _re.sub(r"\s+", " ", t).strip()
                return t

            ref_n = _normalize_for_wer(reference)
            hyp_n = _normalize_for_wer(hypothesis)
            return float(jiwer.wer(ref_n, hyp_n))  # type: ignore
        except Exception as e:
            logger.warning(f"jiwer calculation failed, falling back to basic implementation: {e}")

    # Fallback basic implementation
    import re

    def normalize_text(text: str) -> str:
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()
    if not ref:
        return 1.0 if hyp else 0.0

    m, n = len(ref), len(hyp)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return float(dp[m][n] / len(ref))


def get_audio_duration_seconds(audio_path: str) -> float:
    p = Path(audio_path)
    if not p.exists():
        logger.warning(f"Audio file does not exist: {audio_path}")
        return 0.0
    ext = p.suffix.lower()

    # Method 1: mutagen
    if MutagenFile is not None:
        try:
            mf = MutagenFile(str(p))
            if mf is not None and hasattr(mf, 'info') and hasattr(mf.info, 'length'):
                duration = float(mf.info.length)
                if 0 < duration <= 86400:
                    return duration
        except Exception:
            pass

    # Method 2: wave
    if ext in ['.wav', '.wave']:
        try:
            with wave.open(str(p), 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    duration = frames / float(rate)
                    if 0 < duration <= 86400:
                        return duration
        except Exception:
            pass

    # Method 3: size-based estimate
    try:
        file_size = p.stat().st_size
        if ext == '.mp3':
            duration = (file_size * 8) / 128000.0
        elif ext in ['.wav', '.wave']:
            duration = file_size / (44100 * 2 * 2)
        elif ext in ['.m4a', '.aac', '.mp4']:
            duration = (file_size * 8) / 128000.0
        elif ext in ['.flac']:
            duration = file_size / (1024 * 1024 / 60.0)
        elif ext in ['.ogg', '.opus']:
            duration = (file_size * 8) / 128000.0
        else:
            duration = (file_size * 8) / 128000.0
        if 0 < duration <= 86400:
            return duration
    except Exception:
        logger.warning(f"Size-based estimation failed for {audio_path}")

    logger.warning(f"Unable to determine duration for {audio_path}")
    return 0.0


def calculate_rtf(latency: float, audio_duration: float, metric_name: str = "RTF") -> Optional[float]:
    if not audio_duration or audio_duration <= 0:
        logger.debug(f"{metric_name}: Invalid audio duration {audio_duration}")
        return None
    if latency < 0:
        logger.warning(f"{metric_name}: Negative latency {latency}")
        return None
    rtf = latency / audio_duration
    if rtf > 100:
        logger.warning(f"{metric_name}: Unusually high RTF ({rtf:.4f})")
    return float(rtf)


def get_precision_timer():
    return time.perf_counter


def validate_confidence(confidence: float, vendor: str = "unknown") -> float:
    if confidence is None:
        logger.debug(f"Confidence is None for {vendor}, defaulting to 0.0")
        return 0.0
    try:
        conf = float(confidence)
    except (ValueError, TypeError):
        logger.warning(f"Invalid confidence type for {vendor}: {type(confidence)}")
        return 0.0
    if conf < 0.0:
        return 0.0
    if conf > 1.0:
        if conf >= 2.0 and conf <= 100.0:
            return conf / 100.0
        return 1.0
    return conf


