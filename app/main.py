from dotenv import load_dotenv
load_dotenv()

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
from app.services.tts_minimax import MiniMaxTTSService
from app.services.video import VideoService
from app.services.youtube import youtube_service
from app.utils.text import split_text

tts_service = TTSService()
tts_service_minimax = MiniMaxTTSService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bedtime Story Pipeline")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def home(request: Request):
    base_path = os.getenv("BASE_PATH", "")
    return templates.TemplateResponse("tasks.html", {"request": request, "base_path": base_path})

@app.get("/tasks")
async def tasks_page(request: Request):
    base_path = os.getenv("BASE_PATH", "")
    return templates.TemplateResponse("tasks.html", {"request": request, "base_path": base_path})

image_service = ImageService()
tts_service = TTSService()
video_service = VideoService()

class GenerateRequest(BaseModel):
    story_text: str

async def process_task(task_id: str, tts_provider: str = "edge"):
    task = await task_manager.get_task(task_id)
    if not task:
        return
    
    # Select TTS service based on provider
    if tts_provider == "minimax":
        tts_svc = tts_service_minimax
    else:
        tts_svc = tts_service
    
    try:
        async with asyncio.timeout(1800):
            task.progress = 10
            await task_manager.update_task(task)
            
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
                tts_svc.generate_for_segments(segments, f"{task_dir}/audio")
            )
            
            image_paths, audio_paths = await asyncio.gather(image_task, audio_task)
            task.progress = 60
            await task_manager.update_task(task)
            
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
            
            await task_manager.update_task(task)
    
    except asyncio.TimeoutError:
        task.status = TaskStatus.FAILED
        task.error = {"code": "TASK_TIMEOUT", "message": "任务超时"}
        await task_manager.update_task(task)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = {"code": "TASK_ERROR", "message": str(e)}
        await task_manager.update_task(task)
    
    finally:
        await task_manager.complete_task(task_id)

@app.post("/api/generate")
async def generate_video(request: Request):
    body = await request.json()
    story_text = body.get("story_text", "").strip()
    tts_provider = body.get("tts_provider", "edge")  # "edge" or "minimax"
    
    if not story_text:
        return JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "故事文本不能为空"}},
            status_code=400
        )
    
    try:
        task = await task_manager.create_task(story_text)
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "TASK_QUEUE_FULL", "message": str(e)}},
            status_code=429
        )
    
    asyncio.create_task(process_task(task.task_id, tts_provider))
    
    return {"task_id": task.task_id, "status": "processing"}

@app.post("/api/upload-images/{task_id}")
async def upload_images(task_id: str, request: Request):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    
    try:
        form = await request.form()
        files = form.getlist("images")
        
        if not files:
            return JSONResponse(
                {"error": {"code": "NO_IMAGES", "message": "没有上传图片"}},
                status_code=400
            )
        
        task_dir = f"static/tasks/{task_id}"
        os.makedirs(f"{task_dir}/images", exist_ok=True)
        
        image_paths = []
        for i, file in enumerate(files):
            content = await file.read()
            image_path = f"{task_dir}/images/image_{i}.png"
            with open(image_path, "wb") as f:
                f.write(content)
            image_paths.append(image_path)
        
        task.image_paths = image_paths
        await task_manager.update_task(task)
        
        return {"status": "ok", "image_count": len(image_paths)}
    
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "UPLOAD_ERROR", "message": str(e)}},
            status_code=500
        )

@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "progress": task.progress,
        "story_text": task.story_text,
        "video_url": task.video_url,
        "youtube_url": task.youtube_url,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None
    }

@app.delete("/api/task/{task_id}")
async def cancel_task(task_id: str):
    success = await task_manager.cancel_task(task_id)
    if not success:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    return {"task_id": task_id, "status": "cancelled"}

@app.get("/api/tasks")
async def list_tasks(page: int = 1, page_size: int = 10):
    all_tasks = await task_manager.list_tasks()
    all_tasks.sort(key=lambda t: t.created_at or "", reverse=True)
    
    total = len(all_tasks)
    total_pages = (total + page_size - 1) // page_size
    
    completed_tasks = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
    completed_count = len(completed_tasks)
    
    start = (page - 1) * page_size
    end = start + page_size
    tasks = all_tasks[start:end]
    
    return {
        "tasks": [
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "progress": task.progress,
                "story_text": task.story_text,
                "video_url": task.video_url,
                "youtube_url": task.youtube_url,
                "error": task.error,
                "created_at": task.created_at.isoformat() if task.created_at else None
            }
            for task in tasks
        ],
        "count": total,
        "completed_count": completed_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "processing_count": task_manager._processing_count
    }

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

@app.post("/api/upload-youtube/{task_id}")
async def upload_to_youtube(task_id: str):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    
    if task.status != TaskStatus.COMPLETED or not task.video_url:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_COMPLETED", "message": "任务未完成，无法上传"}},
            status_code=400
        )
    
    if task.youtube_url:
        return {"youtube_url": task.youtube_url, "message": "视频已上传过"}
    
    video_path = f".{task.video_url}"
    if not os.path.exists(video_path):
        return JSONResponse(
            {"error": {"code": "VIDEO_NOT_FOUND", "message": "视频文件不存在"}},
            status_code=404
        )
    
    try:
        result = youtube_service.upload_video(
            video_path=video_path,
            title=f"睡前故事: {task.story_text[:50]}",
            description=task.story_text
        )
        
        task.youtube_url = result['video_url']
        await task_manager.update_task(task)
        
        return {"youtube_url": result['video_url'], "message": "上传成功"}
        
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "UPLOAD_FAILED", "message": str(e)}},
            status_code=500
        )

@app.on_event("startup")
async def startup():
    await task_manager.init()
    asyncio.create_task(cleanup_old_files())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
