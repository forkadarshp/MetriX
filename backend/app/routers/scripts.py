from fastapi import APIRouter

from ..db import get_db_connection, dict_factory


router = APIRouter(prefix="/api", tags=["scripts"])


async def get_scripts_internal():
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


@router.get("/scripts")
async def api_get_scripts():
    return await get_scripts_internal()


