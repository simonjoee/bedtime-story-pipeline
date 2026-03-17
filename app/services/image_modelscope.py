import asyncio
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

class ModelScopeImageService:
    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        self.model = os.getenv("DASHSCOPE_MODEL", "wanx2.1-t2i-turbo")
        self.size = "1280*720"
        self.timeout = 300
    
    async def generate_image(self, prompt: str, output_path: str) -> bool:
        try:
            logger.info(f"Generating image with ModelScope: {prompt[:50]}...")
            
            async with asyncio.timeout(self.timeout):
                task_id = await self._create_task(prompt)
                
                result = await self._wait_for_result(task_id)
                
                image_url = result["output"]["results"][0]["url"]
                
                await self._download_image(image_url, output_path)
            
            logger.info(f"Image saved: {output_path}")
            return True
        except asyncio.TimeoutError:
            logger.error("ModelScope image generation timeout")
            raise
        except Exception as e:
            logger.error(f"ModelScope image generation failed: {e}")
            raise
    
    async def _create_task(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-DashScope-Async": "enable",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": {"prompt": prompt},
            "parameters": {
                "size": self.size,
                "n": 1
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ModelScope API error: {response.status} - {error_text}")
                
                data = await response.json()
                return data["request_id"]
    
    async def _wait_for_result(self, task_id: str, max_wait: int = 300) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        
        async with aiohttp.ClientSession() as session:
            for _ in range(max_wait):
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        await asyncio.sleep(2)
                        continue
                    
                    data = await response.json()
                    task_status = data.get("output", {}).get("task_status", "PENDING")
                    
                    if task_status == "SUCCEEDED":
                        return data
                    elif task_status in ["FAILED", "CANCELLED"]:
                        raise Exception(f"Task {task_status.lower()}: {data.get('message', 'Unknown error')}")
                    
                    await asyncio.sleep(3)
            
            raise Exception("Generation timeout")
    
    async def _download_image(self, url: str, output_path: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image: {response.status}")
                
                content = await response.read()
                with open(output_path, "wb") as f:
                    f.write(content)
    
    async def generate_for_segments(self, segments: list[str], output_dir: str) -> tuple[list[str], list[dict]]:
        os.makedirs(output_dir, exist_ok=True)
        
        image_paths = []
        errors = []
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"image_{i}.png")
            try:
                success = await self.generate_image(segment, output_path)
                if success:
                    image_paths.append(output_path)
                else:
                    logger.warning(f"Failed to generate image for segment {i}")
                    errors.append({"segment": i, "error": "生成失败"})
            except Exception as e:
                logger.error(f"Error generating image for segment {i}: {e}")
                errors.append({"segment": i, "error": str(e)})
        return image_paths, errors
