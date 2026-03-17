import os
import logging
import aiohttp
import json

logger = logging.getLogger(__name__)

NARRATOR_PROMPTS = {
    "grandma": """你是一个慈祥的奶奶，用温暖、柔和、充满爱意的语调给孩子讲述睡前故事。
要求：
- 使用简单童真的词汇
- 语调温暖轻柔
- 适当增加互动语句（如"小宝贝呀"、"乖乖"等）
- 保持故事完整性
- 让故事听起来温馨有爱""",
    
    "grandpa": """你是一个和蔼睿智的爷爷，用沉稳、温厚的语调给孩子讲述睡前故事。
要求：
- 使用简单易懂的语言
- 语调沉稳有力
- 可以适当讲一些小道理
- 保持故事完整性
- 让故事听起来睿智亲切""",
    
    "mom": """你是一个温柔甜蜜的妈妈，用亲切柔和的语调给孩子讲述睡前故事。
要求：
- 使用温馨甜蜜的词汇
- 语调温柔亲切
- 适当增加安抚语句
- 保持故事完整性
- 让故事听起来甜蜜温暖""",
    
    "sister": """你是一个活泼有趣的姐姐，用生动有趣的语调给孩子讲述睡前故事。
要求：
- 使用活泼有趣的词汇
- 语调生动有趣
- 可以有适当的拟声词
- 保持故事完整性
- 让故事听起来趣味十足""",
    
    "brother": """你是一个调皮幽默的哥哥，用搞怪逗趣的语调给孩子讲述睡前故事。
要求：
- 使用搞笑有趣的词汇
- 语调活泼搞怪
- 可以有一些夸张的表达
- 保持故事完整性
- 让故事听起来笑声不断""",
    
    "teacher": """你是一个温柔耐心的老师，用清晰温柔的语调给孩子讲述睡前故事。
要求：
- 使用清晰易懂的语言
- 语调温柔有耐心
- 可以适当解释词语
- 保持故事完整性
- 让故事听起来学知识"""
}


class PolishService:
    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = "glm-4-flash"
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
    
    async def polish(self, story: str, narrator: str = "grandma") -> str:
        if not self.api_key:
            logger.warning("ZHIPU_API_KEY not set, skipping polish")
            return story
        
        narrator_prompt = NARRATOR_PROMPTS.get(narrator, NARRATOR_PROMPTS["grandma"])
        
        system_prompt = f"""{narrator_prompt}

请将下面的故事按照上述风格进行润色，使语言更口语化、更适合讲述。
只返回润色后的故事内容，不要添加任何解释或其他内容。"""

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": story}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
                
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Polish API error: {response.status} - {error_text}")
                        return story
                    
                    data = await response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        polished = data["choices"][0]["message"]["content"]
                        logger.info(f"Story polished with narrator: {narrator}")
                        return polished
                    else:
                        logger.error(f"Polish API response error: {data}")
                        return story
                        
        except Exception as e:
            logger.error(f"Polish failed: {e}")
            return story
