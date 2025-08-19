from typing import Optional, List

from fastapi import APIRouter, HTTPException

from ..db import get_db_connection


router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/dashboard/latency_percentiles")
async def get_latency_percentiles(metric: str = "e2e_latency", days: int = 7):
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
        values: List[float] = []
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


