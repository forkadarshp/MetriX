import json
import uuid
import asyncio
from typing import Any, Dict, List, Optional

from ..db import get_db_connection
from ..utils import calculate_wer, calculate_rtf, get_audio_duration_seconds
from ..vendors import VENDOR_ADAPTERS
from ..config import logger, debug_log


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


async def process_isolated_mode(item_id: str, vendor: str, text_input: str, conn) -> None:
    cursor = conn.cursor()
    cfg = _get_run_config_for_item(conn, item_id)
    service = (cfg.get("service") or ("tts" if vendor in ["elevenlabs", "aws"] else "stt")).lower()

    def pick_models(vendor_name: str, svc: str) -> Dict[str, Any]:
        models = (cfg.get("models") or {}).get(vendor_name, {})
        if vendor_name == "elevenlabs" and svc == "tts":
            return {"model_id": models.get("tts_model") or "eleven_flash_v2_5", "voice": models.get("voice_id") or "21m00Tcm4TlvDq8ikWAM"}
        if vendor_name == "elevenlabs" and svc == "stt":
            return {"model_id": models.get("stt_model") or "scribe_v1"}
        if vendor_name == "deepgram" and svc == "stt":
            return {"model": models.get("stt_model") or "nova-3"}
        if vendor_name == "deepgram" and svc == "tts":
            tts_model = models.get("tts_model") or "aura-2"
            voice = models.get("voice") or "thalia"
            try:
                alias = str(tts_model)
                if alias.startswith("aura-2-") and "-" in alias[7:]:
                    parts = alias.split("-")
                    if len(parts) >= 3:
                        tts_model = "aura-2"
                        voice = parts[2] if parts[1] == "2" else parts[1]
            except Exception:
                pass
            result = {"model": tts_model, "voice": voice}
            debug_log(f"Deepgram TTS pick_models result: {result}")
            return result
        if vendor_name == "aws" and svc == "tts":
            result = {"voice": models.get("voice_id") or "Joanna", "engine": models.get("engine") or "neural"}
            logger.info(f"Picked models for AWS TTS: {result}")
            return result
        return {}

    if service == "tts":
        adapter = VENDOR_ADAPTERS[vendor]["tts"]
        tts_params = pick_models(vendor, "tts")
        debug_log(f"TTS synthesis params for {vendor}: {tts_params}")
        tts_result = await adapter.synthesize(text_input, **tts_params)
        if tts_result.get("status") == "success":
            audio_path = tts_result["audio_path"]
            tts_meta = tts_result.get("metadata", {})
            metrics_meta = {
                "service_type": "tts",
                "vendor": vendor,
                "tts_vendor": vendor,
                "tts_model": tts_meta.get("model"),
                "voice_id": tts_meta.get("voice_id"),
            }
            cursor.execute("UPDATE run_items SET audio_path = ?, metrics_json = ? WHERE id = ?", (audio_path, json.dumps(metrics_meta), item_id))
            duration = float(tts_result.get("duration") or 0.0)
            if not duration or duration <= 0:
                duration = get_audio_duration_seconds(audio_path)
            tts_latency = float(tts_result.get("latency") or 0.0)
            tts_ttfb = float(tts_result.get("ttfb") or 0.0)
            debug_log(f"TTS RTF calculation: vendor={vendor}, latency={tts_latency}, duration={duration}, audio_path={audio_path}")
            tts_rtf = calculate_rtf(tts_latency, duration, "TTS RTF")
            metrics = [
                {"name": "tts_latency", "value": tts_latency, "unit": "seconds"},
                {"name": "audio_duration", "value": duration, "unit": "seconds"},
            ]
            if tts_ttfb is not None and tts_ttfb > 0:
                metrics.append({"name": "tts_ttfb", "value": tts_ttfb, "unit": "seconds"})
            if tts_rtf is not None:
                metrics.append({"name": "tts_rtf", "value": tts_rtf, "unit": "x"})
            dg_params = pick_models("deepgram", "stt")
            stt_adapter = VENDOR_ADAPTERS["deepgram"]["stt"]
            # Disable smart_format so numerical/currency formatting does not
            # inflate WER. We normalize with jiwer in calculate_wer.
            stt_result = await stt_adapter.transcribe(audio_path, **dg_params, smart_format=False, punctuate=True, language="en-US")
            if stt_result.get("status") == "success":
                wer = calculate_wer(text_input, stt_result["transcript"].strip())
                metrics.extend([
                    {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
                ])
            for metric in metrics:
                metric_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO metrics (id, run_item_id, metric_name, value, unit, threshold, pass_fail)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (metric_id, item_id, metric["name"], metric["value"], metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")),
                )
            artifact_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO artifacts (id, run_item_id, type, file_path)
                VALUES (?, ?, 'audio', ?)
                """,
                (artifact_id, item_id, audio_path),
            )
            transcript_text = stt_result.get("transcript") if 'stt_result' in locals() else None
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
                stt_rtf = calculate_rtf(stt_latency, duration, "STT RTF")
                existing_meta = {}
                try:
                    cursor.execute("SELECT metrics_json FROM run_items WHERE id = ?", (item_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        existing_meta = json.loads(row[0])
                except Exception:
                    existing_meta = {}
                stt_meta = stt_result.get("metadata", {})
                merged_meta = {**existing_meta, **{"service_type": "stt", "vendor": vendor, "stt_vendor": vendor, "stt_model": stt_meta.get("model"), "language": stt_meta.get("language")}}
                cursor.execute(
                    "UPDATE run_items SET transcript = ?, audio_path = ?, metrics_json = ? WHERE id = ?",
                    (stt_result["transcript"], audio_path, json.dumps(merged_meta), item_id),
                )
                metrics = [
                    {"name": "wer", "value": wer, "unit": "ratio", "threshold": 0.15, "pass_fail": "pass" if wer <= 0.15 else "fail"},
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
                        (metric_id, item_id, metric["name"], metric["value"], metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")),
                    )
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


async def process_chained_mode(item_id: str, vendor: str, text_input: str, conn) -> None:
    cfg = _get_run_config_for_item(conn, item_id)
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
            tts_model = models.get("tts_model") or "aura-2"
            voice = models.get("voice") or "thalia"
            try:
                alias = str(tts_model)
                if alias.startswith("aura-2-") and "-" in alias[7:]:
                    parts = alias.split("-")
                    if len(parts) >= 3:
                        tts_model = "aura-2"
                        voice = parts[2] if parts[1] == "2" else parts[1]
            except Exception:
                pass
            result = {"model": tts_model, "voice": voice}
            debug_log(f"Deepgram TTS pick_models result: {result}")
            return result
        if vendor_name == "aws" and svc == "tts":
            result = {"voice": models.get("voice_id") or "Joanna", "engine": models.get("engine") or "neural"}
            logger.info(f"Picked models for AWS TTS: {result}")
            return result
        return {}

    tts_adapter = VENDOR_ADAPTERS[tts_vendor]["tts"]
    tts_params = pick_models(tts_vendor, "tts")
    debug_log(f"Chained TTS synthesis params for {tts_vendor}: {tts_params}")
    tts_result = await tts_adapter.synthesize(text_input, **tts_params)
    if tts_result.get("status") != "success":
        return
    audio_path = tts_result["audio_path"]
    stt_adapter = VENDOR_ADAPTERS[stt_vendor]["stt"]
    stt_params = pick_models(stt_vendor, "stt")
    stt_result = await stt_adapter.transcribe(audio_path, **stt_params)
    if stt_result.get("status") != "success":
        return
    wer = calculate_wer(text_input, stt_result["transcript"])
    tts_latency = float(tts_result.get("latency") or 0.0)
    tts_ttfb = float(tts_result.get("ttfb") or 0.0)
    stt_latency = float(stt_result.get("latency") or 0.0)
    total_latency = tts_latency + stt_latency
    duration = float(tts_result.get("duration") or 0.0)
    if not duration or duration <= 0:
        duration = get_audio_duration_seconds(audio_path)
    tts_rtf = calculate_rtf(tts_latency, duration, "TTS RTF (Chained)")
    stt_rtf = calculate_rtf(stt_latency, duration, "STT RTF (Chained)")
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
                "language": (stt_result.get("metadata") or {}).get("language"),
            }),
            item_id,
        ),
    )
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
        {"name": "audio_duration", "value": duration, "unit": "seconds"},
    ]
    if tts_ttfb is not None and tts_ttfb > 0:
        metrics.append({"name": "tts_ttfb", "value": tts_ttfb, "unit": "seconds"})
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
            (metric_id, item_id, metric["name"], metric["value"], metric.get("unit"), metric.get("threshold"), metric.get("pass_fail")),
        )
    conn.commit()


