# 书籍总结生成睡前故事视频 - 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增"书籍总结"功能 - 用户输入书名，AI 自动获取书籍内容并生成故事化总结，填充到故事文本框后手动生成视频。

**Architecture:** 
- 后端新增 `/api/book-summary` API，调用 ZhipuAI 生成书籍的故事化总结
- 前端新增"书籍总结" Tab，输入书名获取总结，点击"生成视频"后填充内容到现有表单，用户手动确认触发生成
- 复用现有视频生成流程（storyboard → 图片 → TTS → 视频合成）

**Tech Stack:** FastAPI, Jinja2, aiohttp, ZhipuAI API, MiniMax TTS

---

## Chunk 1: 后端 - 书籍总结服务

**Files:**
- Create: `app/services/book_summary.py`
- Modify: `app/main.py` (添加 API 端点)
- Test: `tests/test_book_summary.py`

- [ ] **Step 1: 创建书籍总结服务 `app/services/book_summary.py`**

```python
import os
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

BOOK_SUMMARY_PROMPT = """你是一个温暖的故事讲述者，擅长将书籍内容改编成适合睡前聆听的故事。

请根据用户提供的书名，获取或想象这本书的核心内容，然后将其改编成一个约10分钟时长的睡前故事。

要求：
1. 故事化叙事，语气温柔亲切，适合睡前听
2. 保留原书的核心主题和情感
3. 适当增加互动语句（如"小宝贝"，"乖乖"等）
4. 口语化表达，避免书面语
5. 长度约1500-2000字（10分钟朗读时长）
6. 不要使用引号或对话标记，直接叙述

请直接返回故事文本，不要添加任何解释或其他内容。
"""


class BookSummaryService:
    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = "glm-4-flash"
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"

    async def generate_summary(self, book_name: str) -> dict:
        if not self.api_key:
            logger.warning("ZHIPU_API_KEY not set, returning fallback")
            return {
                "summary": f"从前有一本书叫《{book_name}》，书里讲述了一个温暖的故事...",
                "book_name": book_name
            }

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }

                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": BOOK_SUMMARY_PROMPT},
                        {"role": "user", "content": f"请为《{book_name}》生成一个睡前故事"}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4000
                }

                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Book summary API error: {response.status} - {error_text}")
                        return {
                            "summary": f"从前有一本书叫《{book_name}》，书里讲述了一个温暖的故事...",
                            "book_name": book_name
                        }

                    data = await response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"]
                        return {
                            "summary": content.strip(),
                            "book_name": book_name
                        }
                    else:
                        logger.error(f"Book summary response error: {data}")
                        return {
                            "summary": f"从前有一本书叫《{book_name}》，书里讲述了一个温暖的故事...",
                            "book_name": book_name
                        }

        except Exception as e:
            logger.error(f"Book summary generation failed: {e}")
            return {
                "summary": f"从前有一本书叫《{book_name}》，书里讲述了一个温暖的故事...",
                "book_name": book_name
            }


book_summary_service = BookSummaryService()
```

- [ ] **Step 2: 在 `app/main.py` 中添加 API 端点**

在 `app/main.py` 的 import 部分添加（大约第22行附近）：
```python
from app.services.book_summary import book_summary_service
```

在 `app/main.py` 的 `generate_video` 函数后添加（约第231行后）：
```python
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
```

- [ ] **Step 3: 创建测试文件 `tests/test_book_summary.py`**

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.book_summary import BookSummaryService, BOOK_SUMMARY_PROMPT


@pytest.fixture
def book_summary_service():
    return BookSummaryService()


@pytest.mark.asyncio
async def test_book_summary_service_fallback():
    service = BookSummaryService()
    result = await service.generate_summary("小王子")

    assert "book_name" in result
    assert "summary" in result
    assert result["book_name"] == "小王子"
    assert len(result["summary"]) > 0


@pytest.mark.asyncio
async def test_book_summary_service_no_api_key():
    with patch.dict('os.environ', {'ZHIPU_API_KEY': ''}):
        service = BookSummaryService()
        result = await service.generate_summary("小王子")

        assert result["book_name"] == "小王子"
        assert "从前" in result["summary"]


def test_book_summary_prompt_exists():
    assert len(BOOK_SUMMARY_PROMPT) > 0
    assert "睡前" in BOOK_SUMMARY_PROMPT
```

- [ ] **Step 4: 运行测试验证**

```bash
cd /root/opencode/bedtime-story-pipeline && pytest tests/test_book_summary.py -v
```

预期：PASSED (fallback 模式会通过，因为没有真实的 API key)

- [ ] **Step 5: 提交代码**

```bash
git add app/services/book_summary.py app/main.py tests/test_book_summary.py
git commit -m "feat: add book summary service for generating story summaries from book names"
```

---

## Chunk 2: 前端 - 书籍总结 Tab

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: 在 Tab 栏添加"书籍总结"按钮**

找到 `templates/index.html` 约第1265行：
```html
<div class="tabs">
    <button class="tab-btn" onclick="showTab('generate')" id="nav-generate">✨ 生成故事</button>
    <button class="tab-btn" onclick="showTab('book-summary')" id="nav-book-summary">📚 书籍总结</button>
    <button class="tab-btn active" onclick="showTab('tasks')" id="nav-tasks">📋 历史任务</button>
</div>
```

- [ ] **Step 2: 添加"书籍总结" Tab 的 HTML 内容**

在 `tab-generate` 的 `</div>`（约第1331行）后添加：
```html
<div id="tab-book-summary" class="tab-pane">
    <div class="card">
        <div class="card-title">📚 输入书名</div>
        <div style="display: flex; gap: 12px; margin-bottom: 16px;">
            <input type="text" id="bookName" placeholder="请输入书名，如：小王子" 
                   style="flex: 1; padding: 14px 16px; border: 1px solid var(--border); border-radius: 12px; 
                          background: var(--bg-surface); color: var(--text-primary); font-size: 15px;">
            <button class="btn-primary" id="summaryBtn" onclick="generateBookSummary()" 
                    style="padding: 14px 24px;">
                <span>🔍 生成总结</span>
            </button>
        </div>

        <div class="card-title" style="margin-top: 24px;">📝 故事化总结</div>
        <textarea id="summaryText" placeholder="生成的总结将显示在这里，您可以编辑修改..."
                  style="min-height: 200px;"></textarea>

        <div class="options-grid" style="margin-top: 16px;">
            <div class="option-group">
                <label>图像风格</label>
                <select id="summaryImageStyle">
                    <option value="watercolor">水彩画</option>
                    <option value="cartoon">卡通/动漫</option>
                    <option value="3d">3D动画</option>
                    <option value="illustration">插画</option>
                    <option value="oil_painting">油画</option>
                    <option value="realistic">写实</option>
                </select>
            </div>
            <div class="option-group">
                <label>叙述者</label>
                <select id="summaryNarrator">
                    <option value="grandma">慈祥奶奶</option>
                    <option value="grandpa">和蔼爷爷</option>
                    <option value="mom">温柔妈妈</option>
                    <option value="sister">活泼姐姐</option>
                    <option value="brother">调皮哥哥</option>
                    <option value="teacher">温柔老师</option>
                </select>
            </div>
        </div>

        <button class="btn-primary" id="toStoryBtn" onclick="fillStoryFromSummary()" 
                style="margin-top: 20px; background: linear-gradient(135deg, var(--accent-emerald), #10b981);">
            <span>🎬 生成视频</span>
        </button>
    </div>
</div>
```

- [ ] **Step 3: 添加 JavaScript 函数 `generateBookSummary` 和 `fillStoryFromSummary`**

在 `templates/index.html` 约第2028行（`generateVideo` 函数后）添加：

```javascript
async function generateBookSummary() {
    const bookName = document.getElementById('bookName').value.trim();
    if (!bookName) {
        showToast('请输入书名', 'error');
        return;
    }

    const btn = document.getElementById('summaryBtn');
    btn.disabled = true;
    btn.innerHTML = '<span>⏳ 生成中...</span>';

    try {
        const resp = await fetch(basePath + '/api/book-summary', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ book_name: bookName })
        });
        const data = await resp.json();

        if (data.error) {
            showToast(data.error.message || '生成失败', 'error');
        } else {
            document.getElementById('summaryText').value = data.summary;
            showToast('总结生成成功！', 'success');
        }
    } catch (e) {
        showToast('网络错误: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>🔍 重新生成</span>';
    }
}

function fillStoryFromSummary() {
    const summaryText = document.getElementById('summaryText').value.trim();
    if (!summaryText) {
        showToast('请先生成总结', 'error');
        return;
    }

    const imageStyle = document.getElementById('summaryImageStyle').value;
    const narrator = document.getElementById('summaryNarrator').value;

    // 切换到生成故事 Tab
    showTab('generate');

    // 填充内容到现有表单
    document.getElementById('story').value = summaryText;
    document.getElementById('imageStyle').value = imageStyle;
    document.getElementById('narrator').value = narrator;

    showToast('内容已填入，请检查后点击"开始生成视频"', 'success');

    // 滚动到故事输入框
    document.getElementById('story').scrollIntoView({ behavior: 'smooth', block: 'center' });
}
```

- [ ] **Step 4: 更新 `showTab` 函数以支持新的 tab**

找到 `showTab` 函数（约第1507行），确认它能处理 `book-summary` tab：

```javascript
function showTab(tab) {
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tab).classList.add('active');
    document.getElementById('nav-' + tab).classList.add('active');
    if (tab === 'tasks') loadTasks();
    // book-summary tab 不需要额外操作
}
```

- [ ] **Step 5: 提交代码**

```bash
git add templates/index.html
git commit -m "feat: add book summary tab UI for generating story summaries from book names"
```

---

## 验收标准

1. **功能验收**：
   - 访问首页可以看到新增的"📚 书籍总结" Tab
   - 输入书名点击"生成总结"，能返回故事化总结文本
   - 点击"生成视频"后，内容自动填入"生成故事" Tab 的表单中
   - 用户可以手动修改内容后点击"开始生成视频"

2. **测试验收**：
   - `pytest tests/test_book_summary.py -v` 全部通过

3. **UI 验收**：
   - Tab 切换正常
   - 三个 Tab 都有 `active` 状态样式
   - 输入框、下拉框样式与现有界面一致

---

## 注意事项

1. **API Key 依赖**：书籍总结功能依赖 `ZHIPU_API_KEY`，如果没有配置则返回 fallback 内容
2. **图片风格默认值**：书籍总结 Tab 默认选择"水彩画"风格
3. **用户流程**：用户需要两次确认（生成总结后可编辑、填入后可检查）
4. **复用性**：视频生成逻辑完全复用现有 `/api/generate` 接口
