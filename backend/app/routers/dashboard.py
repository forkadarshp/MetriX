import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..db import get_db_connection, dict_factory


router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@router.get("/dashboard/stats")
async def get_dashboard_stats():
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as total_runs FROM runs WHERE datetime(started_at) > datetime('now','-7 days')")
        total_runs = cursor.fetchone()["total_runs"]
        cursor.execute("SELECT COUNT(*) as completed_runs FROM runs WHERE status='completed' AND datetime(started_at) > datetime('now','-7 days')")
        completed_runs = cursor.fetchone()["completed_runs"]
        cursor.execute("SELECT COUNT(*) as total_items FROM run_items WHERE datetime(created_at) > datetime('now','-7 days')")
        total_items = cursor.fetchone()["total_items"]

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
            "success_rate": round((completed_runs / total_runs * 100) if total_runs > 0 else 100.0, 2),
        }
    finally:
        conn.close()


@router.get("/dashboard/insights")
async def get_dashboard_insights():
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
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
                if tts_vendor:
                    vendor_usage_tts[tts_vendor] = vendor_usage_tts.get(tts_vendor, 0) + 1
                if stt_vendor:
                    vendor_usage_stt[stt_vendor] = vendor_usage_stt.get(stt_vendor, 0) + 1
                if tts_vendor and stt_vendor:
                    key = f"{tts_vendor}|{stt_vendor}"
                    if key not in pairings:
                        pairings[key] = {"tts": tts_vendor, "stt": stt_vendor, "wer_sum": 0.0, "count": 0}
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
        top_pairings.sort(key=lambda x: (-x["tests"], x["avg_wer"]))
        return {"service_mix": service_mix, "vendor_usage": {"tts": vendor_usage_tts, "stt": vendor_usage_stt}, "top_vendor_pairings": top_pairings[:5]}
    finally:
        conn.close()


