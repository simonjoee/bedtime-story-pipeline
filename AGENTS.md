# AGENTS.md - 睡前故事视频生成流水线

## 项目概述

基于 FastAPI 的 Web 应用，用于生成睡前故事视频：
1. 将故事文本分段
2. 生成图片（ImageService - 支持 HuggingFace、Leonardo、ModelScope）
3. 文字转语音（TTSService - Azure、MiniMax）
4. 合成图片+音频为视频（VideoService）

## 命令

```bash
# 安装依赖
cd bedtime-story-pipeline
pip install -r requirements.txt

# 运行应用
python -m app.main
# 运行在 http://0.0.0.0:8000

# 运行所有测试
pytest

# 运行单个测试文件
pytest tests/test_image.py

# 运行单个测试函数
pytest tests/test_image.py::test_image_service_generate
```

## 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `ADMIN_PASSWORD` | 登录密码 | (空 - 无需认证) |
| `SESSION_SECRET` | Session 密钥 | `default-secret-change-me` |
| `HF_API_KEY` | HuggingFace API 密钥 | (空) |
| `MINIMAX_ACCESS_TOKEN` | MiniMax TTS token | (空) |
| `MINIMAX_MODEL` | MiniMax TTS 模型 | `speech-02-turbo` |
| `MINIMAX_VOICE` | MiniMax 语音 | `male-qn-qingse` |
| `IMAGE_PROVIDER` | 图片生成服务商 | `huggingface` |
| `DEMO_MODE` | 使用演示模式 | `false` |
| `BASE_PATH` | 基础 URL 路径 | (空) |
| `TTS_API_KEY` | Azure TTS API 密钥 | (空) |
| `TTS_ENDPOINT` | Azure TTS 端点 | `https://eastus.api.cognitive.microsoft.com` |
| `TTS_VOICE` | Azure TTS 语音 | `zh-CN-YunxiNeural` |
| `CLIENT_SECRETS_FILE` | YouTube OAuth 密钥文件 | `client_secrets.json` |

## 代码风格

### 通用规范
- 使用 **4 个空格** 缩进（不使用 Tab）
- 最大行长度：**100 字符**
- 函数/变量使用 **snake_case**
- 类名使用 **PascalCase**
- 常量使用 **UPPER_SNAKE_CASE**

### 导入顺序
1. 标准库 (`os`, `asyncio`, `logging`)
2. 第三方库 (`fastapi`, `aiohttp`, `pydantic`)
3. 本地应用 (`app.models`, `app.services`)

```python
import os
import asyncio
import logging

import aiohttp
from fastapi import FastAPI

from app.models import Task, TaskStatus
from app.services.tts_edge import TTSService
```

### 类型注解
- 参数和返回值始终使用类型注解
- 可空类型使用 `Optional[X]`
- 使用 `list[X]` 而非 `List[X]`（Python 3.9+）

```python
async def generate_image(self, prompt: str, output_path: str) -> bool:
    ...

video_url: Optional[str] = None
```

### 错误处理
- 可能失败的操作使用 try/except
- 使用 `logger.error()` 记录错误
- 可重试的失败抛出异常（由 `@async_retry` 处理）
- 不可重试的失败返回 `False`
- API 响应使用错误字典：

```python
task.error = {"code": "VIDEO_SYNTHESIS_ERROR", "message": "视频合成失败"}
```

### 异步编程
- 异步函数使用 `async def`
- 并发操作使用 `asyncio.gather()`
- 长任务使用 `asyncio.timeout()`

### 日志记录
```python
logger = logging.getLogger(__name__)
```

### 服务模式
- 在 `app/services/` 创建服务类
- API 调用使用 `@async_retry` 装饰器
- 在 `__init__` 中从环境变量读取配置

```python
class ImageService:
    def __init__(self):
        self.api_key = os.getenv("IMAGE_API_KEY", "")

    @async_retry(max_attempts=3, base_delay=2)
    async def generate_image(self, prompt: str, output_path: str) -> bool:
        ...
```

### 数据模型（Pydantic）
```python
from pydantic import BaseModel
from enum import Enum

class TaskStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"

class Task(BaseModel):
    task_id: str
    status: TaskStatus = TaskStatus.PROCESSING
```

### 测试
- 测试文件放在 `tests/` 目录
- 测试文件名格式：`test_*.py`
- 测试函数名格式：`test_*`
- 异步测试使用 `pytest-asyncio`
- 模拟外部 API 调用

## 文件结构

```
bedtime-story-pipeline/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── models.py            # Pydantic 模型
│   ├── task_manager.py      # 任务管理
│   ├── auth.py              # 认证
│   ├── middleware.py        # 中间件
│   ├── database.py          # 数据库
│   ├── services/            # 外部服务
│   │   ├── image.py
│   │   ├── image_leonardo.py
│   │   ├── image_modelscope.py
│   │   ├── tts.py
│   │   ├── tts_minimax.py
│   │   ├── video.py
│   │   └── youtube.py
│   └── utils/
│       ├── text.py
│       └── retry.py
├── templates/               # Jinja2 模板
├── tests/                   # 测试文件
├── static/                  # 静态文件
├── .env                     # 环境配置
├── requirements.txt
└── pytest.ini
```

## 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `task_manager.py` |
| 类名 | PascalCase | `TaskManager` |
| 函数 | snake_case | `generate_image` |
| 变量 | snake_case | `task_id` |
| 常量 | UPPER_SNAKE_CASE | `MAX_CONCURRENT` |
| 枚举值 | UPPER_SNAKE_CASE | `TaskStatus.PROCESSING` |

## 重试机制

外部 API 调用使用 `@async_retry` 装饰器：

```python
from app.utils.retry import async_retry

@async_retry(max_attempts=3, base_delay=2)
async def call_external_api(self, text: str) -> bool:
    ...
```
