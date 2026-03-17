from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

class TaskStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PROCESSING
    progress: int = 0
    story_text: str = ""
    video_url: Optional[str] = None
    youtube_url: Optional[str] = None
    error: Optional[dict] = None
    steps: Dict[str, dict] = {}
    created_at: Optional[datetime] = None
