from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import asyncio
import os
import shutil

from app.models import TaskStatus
from app.task_manager import task_manager
from app.services.image import ImageService
from app.services.tts import TTSService
from app.services.video import VideoService
from app.utils.text import split_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bedtime Story Pipeline")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

image_service = ImageService()
tts_service = TTSService()
video_service = VideoService()

class GenerateRequest(BaseModel):
    story_text: str

async def process_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return
    
    try:
        async with asyncio.timeout(1800):
            task.progress = 10
            
            if task.status == TaskStatus.CANCELLED:
                return
            
            segments = split_text(task.story_text)
            
            task_dir = f"static/tasks/{task_id}"
            os.makedirs(f"{task_dir}/images", exist_ok=True)
            os.makedirs(f"{task_dir}/audio", exist_ok=True)
            
            image_task = asyncio.create_task(
                image_service.generate_for_segments(segments, f"{task_dir}/images")
            )
            audio_task = asyncio.create_task(
                tts_service.generate_for_segments(segments, f"{task_dir}/audio")
            )
            
            image_paths, audio_paths = await asyncio.gather(image_task, audio_task)
            task.progress = 60
            
            if task.status == TaskStatus.CANCELLED:
                return
            
            video_path = f"static/videos/{task_id}.mp4"
            success = video_service.synthesize(image_paths, audio_paths, video_path)
            
            if success:
                task.progress = 100
                task.status = TaskStatus.COMPLETED
                task.video_url = f"/static/videos/{task_id}.mp4"
            else:
                task.status = TaskStatus.FAILED
                task.error = {"code": "VIDEO_SYNTHESIS_ERROR", "message": "视频合成失败"}
    
    except asyncio.TimeoutError:
        task.status = TaskStatus.FAILED
        task.error = {"code": "TASK_TIMEOUT", "message": "任务超时"}
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = {"code": "TASK_ERROR", "message": str(e)}
    
    finally:
        task_manager.complete_task(task_id)

@app.post("/api/generate")
async def generate_video(request: Request):
    body = await request.json()
    story_text = body.get("story_text", "").strip()
    
    if not story_text:
        return JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "故事文本不能为空"}},
            status_code=400
        )
    
    try:
        task = task_manager.create_task(story_text)
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "TASK_QUEUE_FULL", "message": str(e)}},
            status_code=429
        )
    
    asyncio.create_task(process_task(task.task_id))
    
    return {"task_id": task.task_id, "status": "processing"}

@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "progress": task.progress,
        "video_url": task.video_url,
        "error": task.error
    }

@app.delete("/api/task/{task_id}")
async def cancel_task(task_id: str):
    success = task_manager.cancel_task(task_id)
    if not success:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    return {"task_id": task_id, "status": "cancelled"}

@app.get("/health")
async def health_check():
    ffmpeg_ok = video_service.check_ffmpeg()
    return JSONResponse({
        "status": "healthy" if ffmpeg_ok else "degraded",
        "services": {
            "ffmpeg": "ok" if ffmpeg_ok else "not found"
        }
    })

async def cleanup_old_files():
    while True:
        await asyncio.sleep(3600)
        try:
            tasks_dir = "static/tasks"
            videos_dir = "static/videos"
            cutoff = datetime.now() - timedelta(hours=24)
            
            if os.path.exists(tasks_dir):
                for task_id in os.listdir(tasks_dir):
                    task_path = os.path.join(tasks_dir, task_id)
                    if os.path.isdir(task_path):
                        mtime = datetime.fromtimestamp(os.path.getmtime(task_path))
                        if mtime < cutoff:
                            shutil.rmtree(task_path)
            
            if os.path.exists(videos_dir):
                for video in os.listdir(videos_dir):
                    video_path = os.path.join(videos_dir, video)
                    if os.path.isfile(video_path):
                        mtime = datetime.fromtimestamp(os.path.getmtime(video_path))
                        if mtime < cutoff:
                            os.remove(video_path)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

@app.on_event("startup")
async def startup():
    asyncio.create_task(cleanup_old_files())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
