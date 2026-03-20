from typing import Dict, Optional
from app.models import Task, TaskStatus, Segment
from app.database import save_task, get_task as db_get_task, get_all_tasks as db_get_all_tasks, init_db, delete_task as db_delete_task
from datetime import datetime
import uuid
import json

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._processing_count = 0
        self._max_concurrent = 2
        self._db_initialized = False
    
    async def init(self):
        if not self._db_initialized:
            await init_db()
            await self._load_tasks_from_db()
            self._db_initialized = True
    
    async def _load_tasks_from_db(self):
        db_tasks = await db_get_all_tasks()
        for row in db_tasks:
            segments_data = json.loads(row['segments']) if row.get('segments') else []
            segments = [Segment(**s) for s in segments_data]
            task = Task(
                task_id=row['task_id'],
                status=TaskStatus(row['status']),
                progress=row['progress'],
                story_text=row['story_text'] or "",
                video_url=row['video_url'],
                youtube_url=row.get('youtube_url'),
                error=json.loads(row['error']) if row.get('error') else None,
                steps=json.loads(row['steps']) if row.get('steps') else {},
                created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                tts_provider=row.get('tts_provider', 'minimax'),
                image_provider=row.get('image_provider', 'huggingface'),
                image_style=row.get('image_style', 'cartoon'),
                narrator=row.get('narrator', 'grandma'),
                segments=segments
            )
            self.tasks[task.task_id] = task
            if task.status == TaskStatus.PROCESSING:
                self._processing_count += 1
    
    async def create_task(self, story_text: str, tts_provider: str = "minimax", image_provider: str = "huggingface", image_style: str = "cartoon", narrator: str = "grandma") -> Task:
        if self._processing_count >= self._max_concurrent:
            raise Exception("当前任务数已达上限，请稍后再试")
        
        task_id = str(uuid.uuid4())
        now = datetime.now()
        task = Task(task_id=task_id, story_text=story_text, created_at=now, tts_provider=tts_provider, image_provider=image_provider, image_style=image_style, narrator=narrator, segments=[])
        self.tasks[task_id] = task
        self._processing_count += 1
        
        await save_task(
            task_id=task_id,
            status=task.status.value,
            progress=task.progress,
            story_text=task.story_text,
            video_url=task.video_url,
            youtube_url=task.youtube_url,
            error=task.error,
            steps=task.steps,
            created_at=now.isoformat(),
            tts_provider=tts_provider,
            image_provider=image_provider,
            image_style=image_style,
            narrator=narrator
        )
        return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    async def update_task(self, task: Task):
        self.tasks[task.task_id] = task
        await save_task(
            task_id=task.task_id,
            status=task.status.value,
            progress=task.progress,
            story_text=task.story_text,
            video_url=task.video_url,
            youtube_url=task.youtube_url,
            error=task.error,
            steps=task.steps,
            created_at=task.created_at.isoformat() if task.created_at else None,
            tts_provider=task.tts_provider,
            image_provider=task.image_provider,
            image_style=task.image_style,
            narrator=task.narrator,
            segments=[s.model_dump() for s in task.segments] if task.segments else None
        )
    
    async def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            self._processing_count -= 1
            await self.update_task(task)
            return True
        return False
    
    async def complete_task(self, task_id: str):
        self._processing_count -= 1
    
    async def delete_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task:
            if task.status == TaskStatus.PROCESSING:
                self._processing_count -= 1
            del self.tasks[task_id]
            await db_delete_task(task_id)
            return True
        return False
    
    async def list_tasks(self) -> list[Task]:
        return list(self.tasks.values())

task_manager = TaskManager()
