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


class StoryboardService:
    def __init__(self):
        self.api_key = os.getenv("ZHIPU_API_KEY", "")
        self.model = "glm-4-flash"
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"
    
    async def generate(self, story: str, narrator: str = "grandma") -> list[dict]:
        if not self.api_key:
            logger.warning("ZHIPU_API_KEY not set, returning original story as single segment")
            return [{"text": story, "image_prompt": "温馨可爱的睡前故事插画，柔和色彩，卡通风格"}]
        
        narrator_prompt = NARRATOR_PROMPTS.get(narrator, NARRATOR_PROMPTS["grandma"])
        
        system_prompt = f"""{narrator_prompt}

请将故事分成多个适合讲述的片段，并为每个片段生成适合AI图片生成的中文描述prompt。
请直接返回JSON数组格式，不要添加任何解释或其他内容。

返回格式：
[
  {{"text": "第一段润色后的故事内容", "image_prompt": "中文图片描述1"}},
  {{"text": "第二段润色后的故事内容", "image_prompt": "中文图片描述2"}}
]

要求：
- 文本用口语化、适合讲述的风格
- image_prompt要具体、生动、适合AI图片生成（使用中文描述）
- 每段长度适中（约30秒以内能读完）
- 根据故事内容合理分段"""

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
                        logger.error(f"Storyboard API error: {response.status} - {error_text}")
                        return [{"text": story, "image_prompt": "a cute bedtime story illustration, soft colors, cartoon style"}]
                    
                    data = await response.json()
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"]
                        
                        try:
                            start = content.find('[')
                            end = content.rfind(']') + 1
                            if start != -1 and end != 0:
                                json_str = content[start:end]
                                segments = json.loads(json_str)
                                logger.info(f"Generated {len(segments)} segments")
                                return segments
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse storyboard JSON: {e}")
                        
                        return [{"text": story, "image_prompt": "a cute bedtime story illustration, soft colors, cartoon style"}]
                    else:
                        logger.error(f"Storyboard API response error: {data}")
                        return [{"text": story, "image_prompt": "a cute bedtime story illustration, soft colors, cartoon style"}]
                        
        except Exception as e:
            logger.error(f"Storyboard generation failed: {e}")
            return [{"text": story, "image_prompt": "a cute bedtime story illustration, soft colors, cartoon style"}]


storyboard_service = StoryboardService()
