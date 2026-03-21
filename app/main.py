from dotenv import load_dotenv
load_dotenv()

import os
import logging
import asyncio
import shutil

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.models import TaskStatus, Segment
from app.task_manager import task_manager
from app.services.image_modelscope import ModelScopeImageService
from app.services.tts_minimax import MiniMaxTTSService
from app.services.video import VideoService
from app.services.youtube import youtube_service
from app.services.storyboard import storyboard_service
from app.services.book_summary import book_summary_service

from app.auth import verify_password, create_session, delete_session, get_session, COOKIE_NAME, cleanup_expired_sessions
from app.middleware import AuthMiddleware

tts_service_minimax = MiniMaxTTSService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Bedtime Story Pipeline")
app.add_middleware(AuthMiddleware)

BASE_PATH = os.getenv("BASE_PATH", "")
DATA_DIR = os.getenv("DATA_DIR", "data")

app.mount(f"{BASE_PATH}/static", StaticFiles(directory=DATA_DIR), name="static")
templates = Jinja2Templates(directory="templates")

@app.get(f"{BASE_PATH}/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "base_path": BASE_PATH})

@app.get(f"{BASE_PATH}/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "base_path": BASE_PATH})

@app.get(f"{BASE_PATH}/tasks")
async def tasks_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "base_path": BASE_PATH})

modelscope_image_service = ModelScopeImageService()
video_service = VideoService()

async def process_task(task_id: str, tts_provider: str = "minimax", image_provider: str = "modelscope", image_style: str = "cartoon", narrator: str = "grandma"):
    task = await task_manager.get_task(task_id)
    if not task:
        return
    
    tts_provider = task.tts_provider or tts_provider
    image_provider = task.image_provider or image_provider
    image_style = task.image_style or image_style
    
    tts_svc = tts_service_minimax
    
    img_svc = modelscope_image_service
    
    task.steps = {
        "storyboard": {"status": "pending", "message": "等待中"},
        "tts": {"status": "pending", "message": "等待中"},
        "image": {"status": "pending", "message": "等待中"},
        "video": {"status": "pending", "message": "等待中"}
    }
    
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"
    
    if demo_mode:
        raw_segments = [s.strip() for s in task.story_text.replace('\n', '。').split('。') if s.strip()]
        task.segments = [Segment(text=t, image_prompt=t) for t in raw_segments]
        
        task_dir = f"{DATA_DIR}/tasks/{task_id}"
        os.makedirs(f"{task_dir}/images", exist_ok=True)
        os.makedirs(f"{task_dir}/audio", exist_ok=True)
        os.makedirs(f"{DATA_DIR}/videos", exist_ok=True)
        
        video_path = f"{DATA_DIR}/videos/{task_id}.mp4"
        with open(video_path, 'wb') as f:
            f.write(b'DEMO_VIDEO')
        
        task.steps = {
            "storyboard": {"status": "completed", "message": "演示模式"},
            "tts": {"status": "completed", "message": "演示模式"},
            "image": {"status": "completed", "message": "演示模式"},
            "video": {"status": "completed", "message": "演示模式"},
        }
        task.progress = 100
        task.status = TaskStatus.COMPLETED
        task.video_url = f"/static/videos/{task_id}.mp4"
        await task_manager.update_task(task)
        await task_manager.complete_task(task_id)
        return
    
    try:
        async with asyncio.timeout(1800):
            task.progress = 5
            await task_manager.update_task(task)
            
            if task.status == TaskStatus.CANCELLED:
                return
            
            task.steps["storyboard"] = {"status": "processing", "message": "正在生成故事板..."}
            await task_manager.update_task(task)
            
            segments_data = await storyboard_service.generate(task.story_text, narrator)
            task.segments = [Segment(**s) for s in segments_data]
            
            task.steps["storyboard"] = {"status": "completed", "message": f"完成，共 {len(task.segments)} 段"}
            task.progress = 10
            await task_manager.update_task(task)
            
            task_dir = f"{DATA_DIR}/tasks/{task_id}"
            os.makedirs(f"{task_dir}/images", exist_ok=True)
            os.makedirs(f"{task_dir}/audio", exist_ok=True)
            
            segments = task.segments
            texts = [s.text for s in segments]
            prompts = [s.image_prompt for s in segments]
            
            task.steps["tts"] = {"status": "processing", "message": "正在生成音频..."}
            task.steps["image"] = {"status": "processing", "message": "正在生成图像..."}
            await task_manager.update_task(task)
            
            image_task = asyncio.create_task(
                img_svc.generate_for_segments(prompts, f"{task_dir}/images", image_style)
            )
            audio_task = asyncio.create_task(
                tts_svc.generate_for_segments(texts, f"{task_dir}/audio", task.narrator)
            )
            
            image_result, audio_paths = await asyncio.gather(image_task, audio_task)
            image_paths = image_result[0] if isinstance(image_result, tuple) else image_result
            
            for i, path in enumerate(image_paths):
                if i < len(segments):
                    segments[i].image_path = path
            for i, path in enumerate(audio_paths):
                if i < len(segments):
                    segments[i].audio_path = path
            
            if len(audio_paths) < len(segments):
                error_msg = "音频生成失败"
                task.steps["tts"] = {"status": "failed", "message": f"成功 {len(audio_paths)}/{len(segments)} 个片段"}
                task.status = TaskStatus.FAILED
                task.error = {"code": "TTS_ERROR", "message": error_msg}
                await task_manager.update_task(task)
                return
            
            task.steps["tts"] = {"status": "completed", "message": f"完成 {len(audio_paths)} 个片段"}
            
            if len(image_paths) < len(segments):
                error_msg = "图片生成失败"
                task.steps["image"] = {"status": "failed", "message": f"成功 {len(image_paths)}/{len(segments)} 张"}
                task.status = TaskStatus.FAILED
                task.error = {"code": "IMAGE_GENERATION_ERROR", "message": error_msg}
                await task_manager.update_task(task)
                return
            
            task.steps["image"] = {"status": "completed", "message": f"完成 {len(image_paths)} 个片段"}
            task.progress = 60
            await task_manager.update_task(task)
            
            if task.status == TaskStatus.CANCELLED:
                return
            
            task.steps["video"] = {"status": "processing", "message": "正在合成视频..."}
            await task_manager.update_task(task)
            
            video_path = f"{DATA_DIR}/videos/{task_id}.mp4"
            success = video_service.synthesize(image_paths, audio_paths, video_path)
            
            if success:
                task.steps["video"] = {"status": "completed", "message": "视频合成完成"}
                task.progress = 100
                task.status = TaskStatus.COMPLETED
                task.video_url = f"/static/videos/{task_id}.mp4"
            else:
                task.steps["video"] = {"status": "failed", "message": "视频合成失败"}
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

@app.post(f"{BASE_PATH}/api/generate")
async def generate_video(request: Request):
    body = await request.json()
    story_text = body.get("story_text", "").strip()
    tts_provider = body.get("tts_provider", "minimax")  # "minimax" (only supported)
    image_provider = body.get("image_provider", "modelscope")
    image_style = body.get("image_style", "cartoon")  # cartoon, watercolor, realistic, oil_painting, 3d, illustration
    narrator = body.get("narrator", "grandma")  # 讲述人
    
    if not story_text:
        return JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "故事文本不能为空"}},
            status_code=400
        )
    
    try:
        task = await task_manager.create_task(story_text, tts_provider, image_provider, image_style, narrator)
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "TASK_QUEUE_FULL", "message": str(e)}},
            status_code=429
        )
    
    asyncio.create_task(process_task(task.task_id, tts_provider, image_provider, image_style, narrator))
    
    return {"task_id": task.task_id, "status": "processing"}

@app.post(f"{BASE_PATH}/api/book-summary")
async def book_summary(request: Request):
    body = await request.json()
    book_name = body.get("book_name", "").strip()

    if not book_name:
        return JSONResponse(
            {"error": {"code": "INVALID_INPUT", "message": "书名不能为空"}},
            status_code=400
        )

    result = await book_summary_service.generate_summary(book_name)
    return result

@app.post(f"{BASE_PATH}/api/upload-images/{{task_id}}")
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
        
        task_dir = f"{DATA_DIR}/tasks/{task_id}"
        os.makedirs(f"{task_dir}/images", exist_ok=True)
        
        image_paths = []
        for i, file in enumerate(files):
            content = await file.read()
            image_path = f"{task_dir}/images/image_{i}.png"
            with open(image_path, "wb") as f:
                f.write(content)
            image_paths.append(image_path)
        
        await task_manager.update_task(task)
        
        return {"status": "ok", "image_count": len(image_paths)}
    
    except Exception as e:
        return JSONResponse(
            {"error": {"code": "UPLOAD_ERROR", "message": str(e)}},
            status_code=500
        )

@app.get(f"{BASE_PATH}/api/task/{{task_id}}")
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
        "steps": task.steps,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "tts_provider": task.tts_provider,
        "image_provider": task.image_provider,
        "image_style": task.image_style
    }

@app.delete(f"{BASE_PATH}/api/task/{{task_id}}/delete")
async def delete_task_v2(task_id: str):
    success = await task_manager.delete_task(task_id)
    if not success:
        return JSONResponse(
            {"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}},
            status_code=404
        )
    return {"task_id": task_id, "message": "已删除"}

@app.get(f"{BASE_PATH}/api/tasks")
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
                "steps": task.steps,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "tts_provider": task.tts_provider,
                "image_provider": task.image_provider,
                "image_style": task.image_style
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

@app.get(f"{BASE_PATH}/health")
async def health_check():
    return {"status": "ok"}

@app.post(f"{BASE_PATH}/api/login")
async def login(request: Request):
    body = await request.json()
    password = body.get("password", "")
    if verify_password(password):
        session_id = create_session()
        response = JSONResponse({"status": "ok", "message": "登录成功"})
        response.set_cookie(
            key=COOKIE_NAME,
            value=session_id,
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            samesite="lax"
        )
        return response
    return JSONResponse(
        {"error": {"code": "INVALID_PASSWORD", "message": "密码错误"}},
        status_code=401
    )

@app.post(f"{BASE_PATH}/api/logout")
async def logout(request: Request):
    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        delete_session(session_id)
    response = JSONResponse({"status": "ok", "message": "已退出登录"})
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get(f"{BASE_PATH}/api/check-auth")
async def check_auth(request: Request):
    session_id = request.cookies.get(COOKIE_NAME)
    session = get_session(session_id) if session_id else None
    if session:
        return {"authenticated": True}
    return JSONResponse({"authenticated": False}, status_code=401)

async def cleanup_old_files():
    while True:
        await asyncio.sleep(3600)
        try:
            tasks_dir = f"{DATA_DIR}/tasks"
            videos_dir = f"{DATA_DIR}/videos"
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

@app.post(f"{BASE_PATH}/api/upload-youtube/{{task_id}}")
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

@app.get(f"{BASE_PATH}/storyboard/{{task_id}}")
async def storyboard_page(request: Request, task_id: str):
    base_path = os.getenv("BASE_PATH", "")
    return templates.TemplateResponse("storyboard.html", {"request": request, "base_path": base_path, "task_id": task_id})

@app.get(f"{BASE_PATH}/api/storyboard/{{task_id}}")
async def get_storyboard(task_id: str):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}}, status_code=404)
    return {
        "segments": [s.model_dump() for s in task.segments],
        "steps": task.steps,
        "status": task.status.value
    }

@app.put(f"{BASE_PATH}/api/storyboard/{{task_id}}")
async def update_storyboard(task_id: str, request: Request):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}}, status_code=404)
    
    body = await request.json()
    segments_data = body.get("segments", [])
    task.segments = [Segment(**s) for s in segments_data]
    await task_manager.update_task(task)
    return {"status": "ok"}

@app.post(f"{BASE_PATH}/api/regenerate/{{task_id}}")
async def regenerate_task(task_id: str, request: Request):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}}, status_code=404)
    
    body = await request.json()
    edited_indices = body.get("indices", [])
    
    if not edited_indices:
        edited_indices = list(range(len(task.segments)))
    
    tts_svc = tts_service_minimax
    
    img_svc = modelscope_image_service
    
    task_dir = f"{DATA_DIR}/tasks/{task_id}"
    os.makedirs(f"{task_dir}/images", exist_ok=True)
    os.makedirs(f"{task_dir}/audio", exist_ok=True)
    
    for idx in edited_indices:
        if idx < len(task.segments):
            segment = task.segments[idx]
            
            try:
                image_path = f"{task_dir}/images/image_{idx}.png"
                success = await img_svc.generate_image(segment.image_prompt, image_path)
                if success:
                    segment.image_path = image_path
            except Exception as e:
                logger.error(f"Failed to regenerate image for segment {idx}: {e}")
            
            try:
                audio_path = f"{task_dir}/audio/audio_{idx}.mp3"
                success = await tts_svc.text_to_speech(segment.text, audio_path)
                if success:
                    segment.audio_path = audio_path
            except Exception as e:
                logger.error(f"Failed to regenerate audio for segment {idx}: {e}")
    
    await task_manager.update_task(task)
    
    image_paths = [s.image_path for s in task.segments if s.image_path]
    audio_paths = [s.audio_path for s in task.segments if s.audio_path]
    
    if image_paths and audio_paths and len(image_paths) == len(task.segments):
        video_path = f"{DATA_DIR}/videos/{task_id}.mp4"
        video_service.synthesize(image_paths, audio_paths, video_path)
        task.video_url = f"/static/videos/{task_id}.mp4"
        await task_manager.update_task(task)
    
    return {"status": "ok", "video_url": task.video_url}

@app.post(f"{BASE_PATH}/api/regenerate-tts/{{task_id}}")
async def regenerate_tts_task(task_id: str, request: Request):
    task = await task_manager.get_task(task_id)
    if not task:
        return JSONResponse({"error": {"code": "TASK_NOT_FOUND", "message": "任务不存在"}}, status_code=404)
    
    body = await request.json()
    edited_indices = body.get("indices", [])
    
    if not edited_indices:
        edited_indices = list(range(len(task.segments)))
    
    tts_svc = tts_service_minimax
    
    task_dir = f"{DATA_DIR}/tasks/{task_id}"
    os.makedirs(f"{task_dir}/audio", exist_ok=True)
    
    for idx in edited_indices:
        if idx < len(task.segments):
            segment = task.segments[idx]
            
            audio_path = f"{task_dir}/audio/audio_{idx}.mp3"
            success = await tts_svc.text_to_speech(segment.text, audio_path)
            if success:
                segment.audio_path = audio_path
    
    await task_manager.update_task(task)
    
    image_paths = [s.image_path for s in task.segments if s.image_path]
    audio_paths = [s.audio_path for s in task.segments if s.audio_path]
    
    if image_paths and audio_paths and len(image_paths) == len(task.segments):
        video_path = f"{DATA_DIR}/videos/{task_id}.mp4"
        video_service.synthesize(image_paths, audio_paths, video_path)
        task.video_url = f"/static/videos/{task_id}.mp4"
        await task_manager.update_task(task)
    
    return {"status": "ok", "video_url": task.video_url}

@app.on_event("startup")
async def startup():
    await task_manager.init()
    asyncio.create_task(cleanup_old_files())
    asyncio.create_task(cleanup_sessions())

async def cleanup_sessions():
    while True:
        await asyncio.sleep(3600)
        cleanup_expired_sessions()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
