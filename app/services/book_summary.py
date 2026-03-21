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