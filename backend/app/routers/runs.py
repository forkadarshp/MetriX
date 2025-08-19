import json
import csv
from io import StringIO
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, HTTPException

from ..db import get_db_connection, dict_factory
from ..models import RunCreate
from ..services.runs_service import process_isolated_mode, process_chained_mode


router = APIRouter(prefix="/api", tags=["runs"])


@router.post("/runs")
async def create_run(run_data: RunCreate):
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
                json.dumps(run_data.config),
            ),
        )
        test_inputs: List[Dict[str, Any]] = []

        def _add_text(text: Optional[str]):
            if text is None:
                return
            t = str(text).strip()
            if t:
                test_inputs.append({"text": t, "script_item_id": None})

        def _parse_batch_input(raw: Optional[str], fmt: Optional[str]) -> None:
            if not raw:
                return
            format_lower = (fmt or "txt").lower()
            if format_lower == "jsonl":
                for line in StringIO(raw):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        _add_text(obj.get("text") or obj.get("prompt") or obj.get("sentence"))
                    except Exception:
                        # Skip malformed lines
                        continue
            elif format_lower == "csv":
                try:
                    reader = csv.DictReader(StringIO(raw))
                    for row in reader:
                        if not row:
                            continue
                        _add_text(row.get("text") or row.get("prompt") or row.get("sentence"))
                except Exception:
                    # Fallback: treat as plain text if CSV parsing fails
                    for line in StringIO(raw):
                        _add_text(line)
            else:  # txt
                for line in StringIO(raw):
                    _add_text(line)
        if run_data.text_inputs:
            for text in run_data.text_inputs:
                test_inputs.append({"text": text, "script_item_id": None})
        # Direct batch items array
        if getattr(run_data, "batch_script_items", None):
            for item in (run_data.batch_script_items or []):
                try:
                    # item can be dict or model; support both
                    txt = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
                    _add_text(txt)
                except Exception:
                    continue
        # Raw batch input string with format
        if getattr(run_data, "batch_script_input", None):
            _parse_batch_input(run_data.batch_script_input, getattr(run_data, "batch_script_format", None))
        if run_data.script_ids:
            for script_id in run_data.script_ids:
                cursor.execute("SELECT * FROM script_items WHERE script_id = ?", (script_id,))
                items = cursor.fetchall()
                for item in items:
                    test_inputs.append({"text": item[2], "script_item_id": item[0]})
        if not test_inputs:
            test_inputs = [{"text": "Hello world, this is a test.", "script_item_id": None}]
        mode_lower = (run_data.mode or "isolated").lower()
        cfg = run_data.config or {}
        chain = cfg.get("chain") or {}
        tts_vendor = (chain.get("tts_vendor") or "elevenlabs").lower()
        stt_vendor = (chain.get("stt_vendor") or "deepgram").lower()
        combined_label = f"{tts_vendor}→{stt_vendor}"
        if mode_lower == "chained":
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
            cursor.execute("UPDATE runs SET vendor_list_json = ? WHERE id = ?", (json.dumps([combined_label]), run_id))
        else:
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
        import asyncio as _asyncio

        _asyncio.create_task(process_run(run_id))
        return {"run_id": run_id, "status": "created", "message": "Run created and processing started"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create run: {str(e)}")
    finally:
        conn.close()


async def process_run(run_id: str) -> None:
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
            except Exception:
                cursor.execute("UPDATE run_items SET status = 'failed' WHERE id = ?", (item_id,))
                conn.commit()
        cursor.execute("UPDATE runs SET status = 'completed', finished_at = CURRENT_TIMESTAMP WHERE id = ?", (run_id,))
        conn.commit()
    except Exception:
        cursor.execute("UPDATE runs SET status = 'failed' WHERE id = ?", (run_id,))
        conn.commit()
    finally:
        conn.close()


@router.get("/runs")
async def get_runs():
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


@router.get("/runs/{run_id}")
async def get_run_details(run_id: str):
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


@router.post("/runs/quick")
async def create_quick_run(text: str = Form(...), vendors: str = Form(...), mode: str = Form("isolated"), config: Optional[str] = Form(None)):
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
        raise HTTPException(status_code=500, detail=str(e))


