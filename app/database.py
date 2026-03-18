import aiosqlite
import os
import json
from datetime import datetime
from typing import Optional, Dict

DB_PATH = "data/tasks.db"

async def init_db():
    os.makedirs("data", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                progress INTEGER DEFAULT 0,
                story_text TEXT,
                video_url TEXT,
                youtube_url TEXT,
                error TEXT,
                steps TEXT,
                created_at TEXT,
                tts_provider TEXT DEFAULT 'edge',
                image_provider TEXT DEFAULT 'huggingface',
                image_style TEXT DEFAULT 'cartoon',
                polish INTEGER DEFAULT 0,
                narrator TEXT DEFAULT 'grandma',
                segments TEXT
            )
        """)
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN steps TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN tts_provider TEXT DEFAULT 'edge'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN image_provider TEXT DEFAULT 'huggingface'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN image_style TEXT DEFAULT 'cartoon'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN polish INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN narrator TEXT DEFAULT 'grandma'")
        except:
            pass
        try:
            await db.execute("ALTER TABLE tasks ADD COLUMN segments TEXT")
        except:
            pass
        await db.commit()

async def save_task(task_id: str, status: str, progress: int, story_text: str,
                   video_url: Optional[str], error: Optional[dict], created_at: Optional[str],
                   youtube_url: Optional[str] = None, steps: Optional[Dict[str, dict]] = None,
                   tts_provider: Optional[str] = "edge", image_provider: Optional[str] = "huggingface",
                   image_style: Optional[str] = "cartoon", polish: bool = False, narrator: str = "grandma",
                   segments: Optional[list] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO tasks (task_id, status, progress, story_text, video_url, youtube_url, error, steps, created_at, tts_provider, image_provider, image_style, polish, narrator, segments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (task_id, status, progress, story_text, video_url, youtube_url, 
              json.dumps(error) if error else None,
              json.dumps(steps) if steps else None,
              created_at, tts_provider, image_provider, image_style, 1 if polish else 0, narrator,
              json.dumps(segments) if segments else None))
        await db.commit()

async def get_task(task_id: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_all_tasks() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tasks ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def delete_task(task_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        await db.commit()
