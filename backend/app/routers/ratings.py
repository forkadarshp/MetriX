import json
import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..db import get_db_connection, dict_factory
from ..models import UserRatingSubmit


router = APIRouter(prefix="/api", tags=["ratings"])


@router.get("/subjective-metrics")
async def get_subjective_metrics():
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM subjective_metrics ORDER BY service_type, name")
        metrics = cursor.fetchall()
        return {"subjective_metrics": metrics}
    finally:
        conn.close()


@router.get("/subjective-metrics/{service_type}")
async def get_subjective_metrics_by_service(service_type: str):
    if service_type not in ["tts", "stt"]:
        raise HTTPException(status_code=400, detail="Service type must be 'tts' or 'stt'")
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM subjective_metrics WHERE service_type = ? ORDER BY name", (service_type,))
        metrics = cursor.fetchall()
        return {"subjective_metrics": metrics}
    finally:
        conn.close()


@router.post("/user-ratings")
async def submit_user_rating(rating_data: UserRatingSubmit):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM run_items WHERE id = ?", (rating_data.run_item_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Run item not found")
        for metric_id in rating_data.ratings.keys():
            cursor.execute("SELECT id FROM subjective_metrics WHERE id = ?", (metric_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=400, detail=f"Subjective metric '{metric_id}' not found")
        for metric_id, rating in rating_data.ratings.items():
            rating_id = str(uuid.uuid4())
            comment = rating_data.comments.get(metric_id, "") if rating_data.comments else ""
            cursor.execute("SELECT scale_min, scale_max FROM subjective_metrics WHERE id = ?", (metric_id,))
            scale = cursor.fetchone()
            if scale and not (scale[0] <= rating <= scale[1]):
                raise HTTPException(status_code=400, detail=f"Rating {rating} for {metric_id} must be between {scale[0]} and {scale[1]}")
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_ratings 
                (id, run_item_id, user_name, subjective_metric_id, rating, comment)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (rating_id, rating_data.run_item_id, rating_data.user_name, metric_id, rating, comment),
            )
        conn.commit()
        return {"message": "Ratings submitted successfully", "user_name": rating_data.user_name}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit ratings: {str(e)}")
    finally:
        conn.close()


@router.get("/user-ratings/{run_item_id}")
async def get_user_ratings(run_item_id: str):
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 
                ur.subjective_metric_id,
                sm.name,
                sm.description,
                sm.service_type,
                sm.scale_min,
                sm.scale_max,
                AVG(ur.rating) as avg_rating,
                COUNT(ur.rating) as rating_count
            FROM user_ratings ur
            JOIN subjective_metrics sm ON ur.subjective_metric_id = sm.id
            WHERE ur.run_item_id = ?
            GROUP BY ur.subjective_metric_id
            """,
            (run_item_id,),
        )
        avg_ratings = cursor.fetchall()
        cursor.execute(
            """
            SELECT 
                ur.*,
                sm.name as metric_name,
                sm.service_type
            FROM user_ratings ur
            JOIN subjective_metrics sm ON ur.subjective_metric_id = sm.id
            WHERE ur.run_item_id = ?
            ORDER BY ur.created_at DESC
            """,
            (run_item_id,),
        )
        user_ratings = cursor.fetchall()
        cursor.execute(
            """
            SELECT COUNT(DISTINCT ur.user_name) as unique_user_count
            FROM user_ratings ur
            WHERE ur.run_item_id = ?
            """,
            (run_item_id,),
        )
        unique_user_count = cursor.fetchone()["unique_user_count"]
        return {
            "run_item_id": run_item_id,
            "average_ratings": avg_ratings,
            "user_ratings": user_ratings,
            "unique_user_count": unique_user_count,
        }
    finally:
        conn.close()


@router.get("/user-ratings/{run_item_id}/user/{user_name}")
async def get_user_ratings_by_user(run_item_id: str, user_name: str):
    conn = get_db_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT 
                ur.*,
                sm.name as metric_name,
                sm.description,
                sm.service_type,
                sm.scale_min,
                sm.scale_max
            FROM user_ratings ur
            JOIN subjective_metrics sm ON ur.subjective_metric_id = sm.id
            WHERE ur.run_item_id = ? AND ur.user_name = ?
            """,
            (run_item_id, user_name),
        )
        ratings = cursor.fetchall()
        return {"run_item_id": run_item_id, "user_name": user_name, "ratings": ratings}
    finally:
        conn.close()


