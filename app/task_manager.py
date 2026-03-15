from typing import Dict
from app.models import Task, TaskStatus
import uuid

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._processing_count = 0
        self._max_concurrent = 2
    
    def create_task(self, story_text: str) -> Task:
        if self._processing_count >= self._max_concurrent:
            raise Exception("当前任务数已达上限，请稍后再试")
        
        task_id = str(uuid.uuid4())
        task = Task(task_id=task_id, story_text=story_text)
        self.tasks[task_id] = task
        self._processing_count += 1
        return task
    
    def get_task(self, task_id: str) -> Task:
        return self.tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            self._processing_count -= 1
            return True
        return False
    
    def complete_task(self, task_id: str):
        self._processing_count -= 1

task_manager = TaskManager()
