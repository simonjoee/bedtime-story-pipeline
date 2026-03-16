# AGENTS.md - Bedtime Story Pipeline

## Project Overview

This is a FastAPI-based web application that generates bedtime story videos by:
1. Splitting story text into segments
2. Generating images for each segment (via ImageService)
3. Converting text to speech (via TTSService)
4. Synthesizing images + audio into video (via VideoService)

## Commands

### Running the Application

```bash
cd bedtime-story-pipeline
pip install -r requirements.txt
python -m app.main
```

The app runs on `http://0.0.0.0:8000`.

### Running Tests

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_image.py

# Run a single test function
pytest tests/test_image.py::test_image_service_generate
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_API_KEY` | Azure TTS API key | (empty - demo mode) |
| `TTS_ENDPOINT` | Azure TTS endpoint | `https://eastus.api.cognitive.microsoft.com` |
| `TTS_VOICE` | TTS voice name | `zh-CN-YunxiNeural` |
| `IMAGE_API_KEY` | Image generation API key | (empty) |
| `IMAGE_ENDPOINT` | Image generation endpoint | (empty) |
| `IMAGE_PROVIDER` | Image provider | `leonardo` |
| `DEMO_MODE` | Use demo/placeholder mode | `true` |
| `BASE_PATH` | Base path for URLs | (empty) |

## Code Style Guidelines

### General

- Use **4 spaces** for indentation (no tabs)
- Maximum line length: **100 characters**
- Use **snake_case** for functions and variables
- Use **PascalCase** for class names
- Use **UPPER_SNAKE_CASE** for constants

### Imports

Order imports as:
1. Standard library (`os`, `asyncio`, `logging`)
2. Third-party (`fastapi`, `aiohttp`, `pydantic`)
3. Local application (`app.models`, `app.services`)

```python
import os
import asyncio
import logging

import aiohttp
from fastapi import FastAPI

from app.models import Task, TaskStatus
from app.services.tts import TTSService
```

### Type Hints

Always use type hints for function parameters and return values:

```python
async def generate_image(self, prompt: str, output_path: str) -> bool:
    ...
```

Use `Optional[X]` for nullable types:
```python
video_url: Optional[str] = None
```

Use `list[str]` instead of `List[str]` (Python 3.9+).

### Error Handling

- Use try/except blocks for operations that may fail
- Always log errors with `logger.error()`
- Raise exceptions for retryable failures (handled by `@async_retry`)
- Return `False` for non-retryable failures
- Use descriptive error dictionaries for API responses:

```python
task.error = {"code": "VIDEO_SYNTHESIS_ERROR", "message": "视频合成失败"}
```

### Async/Await

- Use `async def` for async functions
- Use `asyncio.gather()` for concurrent operations
- Use `asyncio.timeout()` for long-running tasks
- Use `asyncio.create_task()` for fire-and-forget background tasks

### Logging

Use the module-level logger pattern:

```python
logger = logging.getLogger(__name__)
```

Log levels:
- `logger.debug()` - Detailed debugging info
- `logger.info()` - Normal operation events
- `logger.warning()` - Warning conditions
- `logger.error()` - Errors

### Services Pattern

Follow the existing service pattern:
- Create service classes in `app/services/`
- Use `@async_retry` decorator for API calls
- Read config from environment variables in `__init__`
- Use snake_case method names

```python
class ImageService:
    def __init__(self):
        self.api_key = os.getenv("IMAGE_API_KEY", "")
        ...
    
    @async_retry(max_attempts=3, base_delay=2)
    async def generate_image(self, prompt: str, output_path: str) -> bool:
        ...
```

### Models

Use Pydantic for data models:

```python
from pydantic import BaseModel
from enum import Enum

class TaskStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    ...

class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PROCESSING
    ...
```

### Testing

- Place tests in `tests/` directory
- Name test files as `test_*.py`
- Name test functions as `test_*`
- Use `pytest-asyncio` for async tests
- Mock external API calls in tests

### File Structure

```
bedtime-story-pipeline/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── models.py            # Pydantic models
│   ├── task_manager.py      # Task management
│   ├── routers/             # API routers (future)
│   ├── services/            # External service integrations
│   │   ├── image.py
│   │   ├── tts.py
│   │   └── video.py
│   └── utils/               # Utility functions
│       ├── text.py
│       └── retry.py
├── static/                  # Static files (generated videos, etc.)
├── templates/               # Jinja2 templates
├── tests/                  # Test files
├── requirements.txt
└── pytest.ini
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Files | snake_case | `task_manager.py` |
| Classes | PascalCase | `TaskManager` |
| Functions | snake_case | `generate_image` |
| Variables | snake_case | `task_id`, `audio_paths` |
| Constants | UPPER_SNAKE_CASE | `MAX_CONCURRENT` |
| Enum values | UPPER_SNAKE_CASE | `TaskStatus.PROCESSING` |

### Retries

Use the `@async_retry` decorator for any external API calls:

```python
from app.utils.retry import async_retry

@async_retry(max_attempts=3, base_delay=2)
async def call_external_api(self, text: str) -> bool:
    ...
```
