from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ScriptCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[str] = None


class ScriptItemCreate(BaseModel):
    script_id: str
    text: str
    lang: str = "en-US"
    tags: Optional[str] = None


class BatchScriptItem(BaseModel):
    text: str
    lang: Optional[str] = "en-US"
    tags: Optional[str] = None


class RunCreate(BaseModel):
    project_id: Optional[str] = "default_project"
    mode: Literal["isolated", "chained"]
    vendors: List[str]
    config: Optional[Dict[str, Any]] = {}
    text_inputs: Optional[List[str]] = None
    script_ids: Optional[List[str]] = None
    # New: allow providing a script directly as batched input
    batch_script_items: Optional[List[BatchScriptItem]] = None
    batch_script_input: Optional[str] = None  # raw payload (JSONL/CSV/TXT)
    batch_script_format: Optional[Literal["jsonl", "csv", "txt"]] = None


class QuickRunForm(BaseModel):
    text: str
    vendors: List[str]
    mode: Literal["isolated", "chained"]
    config: Optional[Dict[str, Any]] = {}


class MetricResult(BaseModel):
    name: str
    value: float
    unit: Optional[str] = None
    threshold: Optional[float] = None
    pass_fail: Optional[str] = None


class UserRatingSubmit(BaseModel):
    run_item_id: str
    user_name: str
    ratings: Dict[str, int]  # subjective_metric_id -> rating
    comments: Optional[Dict[str, str]] = {}  # subjective_metric_id -> comment


