import io
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..db import get_db_connection, dict_factory


router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export")
async def export_results(payload: Dict[str, Any]):
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
        norm: List[Dict[str, Any]] = []
        for row in rows:
            metrics_map: Dict[str, Any] = {}
            if row.get("metrics_summary"):
                for kv in row["metrics_summary"].split("|"):
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        try:
                            metrics_map[k] = float(v)
                        except Exception:
                            metrics_map[k] = v
            subjective_ratings: Dict[str, Any] = {}
            item_id = row.get("id")
            try:
                cursor.execute(
                    """
                    SELECT 
                        sm.name,
                        AVG(ur.rating) as avg_rating,
                        COUNT(ur.rating) as rating_count
                    FROM user_ratings ur
                    JOIN subjective_metrics sm ON ur.subjective_metric_id = sm.id
                    WHERE ur.run_item_id = ?
                    GROUP BY ur.subjective_metric_id
                    """,
                    (item_id,),
                )
                rating_results = cursor.fetchall()
                for rating_row in rating_results:
                    rating_name = rating_row["name"].replace(" ", "_").lower()
                    avg_rating = round(rating_row["avg_rating"], 2)
                    rating_count = rating_row["rating_count"]
                    subjective_ratings[f"subj_{rating_name}"] = avg_rating
                    subjective_ratings[f"subj_{rating_name}_count"] = rating_count
            except Exception:
                pass
            service = "UNKNOWN"
            if "e2e_latency" in metrics_map:
                service = "E2E"
            elif ("stt_latency" in metrics_map) or ("wer" in metrics_map):
                service = "STT"
            elif "tts_latency" in metrics_map:
                service = "TTS"
            row_data = {
                "run_id": row.get("run_id"),
                "run_item_id": row.get("id"),
                "started_at": row.get("started_at"),
                "mode": row.get("mode"),
                "vendor": row.get("vendor"),
                "service": service,
                "text_input": row.get("text_input"),
                "transcript": row.get("transcript"),
                "wer": metrics_map.get("wer"),
                "e2e_latency": metrics_map.get("e2e_latency"),
                "tts_latency": metrics_map.get("tts_latency"),
                "stt_latency": metrics_map.get("stt_latency"),
                "tts_ttfb": metrics_map.get("tts_ttfb"),
                "audio_duration": metrics_map.get("audio_duration"),
                "tts_rtf": metrics_map.get("tts_rtf"),
                "stt_rtf": metrics_map.get("stt_rtf"),
                "audio_path": row.get("audio_path"),
            }
            row_data.update(subjective_ratings)
            norm.append(row_data)
        if fmt == "csv":
            output = io.StringIO()
            base_fieldnames = [
                "run_id",
                "run_item_id",
                "started_at",
                "mode",
                "vendor",
                "service",
                "text_input",
                "transcript",
                "wer",
                "e2e_latency",
                "tts_latency",
                "stt_latency",
                "tts_ttfb",
                "audio_duration",
                "tts_rtf",
                "stt_rtf",
                "audio_path",
            ]
            subjective_fieldnames = set()
            for row in norm:
                for key in row.keys():
                    if key.startswith("subj_"):
                        subjective_fieldnames.add(key)
            subjective_fieldnames_list = sorted(list(subjective_fieldnames))
            fieldnames = base_fieldnames + subjective_fieldnames_list
            import csv

            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for r in norm:
                writer.writerow(r)
            csv_bytes = output.getvalue().encode("utf-8")
            headers = {"Content-Disposition": f"attachment; filename=benchmark_export_{int(time.perf_counter())}.csv"}
            return Response(content=csv_bytes, media_type="text/csv", headers=headers)
        elif fmt == "pdf":
            try:
                from reportlab.lib.pagesizes import letter  # type: ignore
                from reportlab.pdfgen import canvas  # type: ignore
                from reportlab.lib.units import inch  # type: ignore
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
                subj_ratings = []
                for key, value in r.items():
                    if key.startswith("subj_") and not key.endswith("_count"):
                        metric_name = key.replace("subj_", "").replace("_", " ").title()
                        count_key = f"{key}_count"
                        count = r.get(count_key, 0)
                        subj_ratings.append(f"{metric_name}: {value}/5 ({count})")
                subj_str = " | ".join(subj_ratings) if subj_ratings else "No ratings"
                line1 = f"{r['started_at']} | {r['mode']} | {r['vendor']} | {r['service']} | WER: {r.get('wer')} | E2E: {r.get('e2e_latency')}s | TTS: {r.get('tts_latency')}s | STT: {r.get('stt_latency')}s"
                line2 = f"User Ratings: {subj_str}"
                for chunk in [line1[i:i+110] for i in range(0, len(line1), 110)]:
                    c.drawString(x_margin, y, chunk)
                    y -= 12
                    if y < 0.75 * inch:
                        c.showPage()
                        c.setFont("Helvetica", 9)
                        y = height - 0.75 * inch
                if subj_ratings:
                    for chunk in [line2[i:i+110] for i in range(0, len(line2), 110)]:
                        c.drawString(x_margin, y, chunk)
                        y -= 12
                        if y < 0.75 * inch:
                            c.showPage()
                            c.setFont("Helvetica", 9)
                            y = height - 0.75 * inch
                y -= 10
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


