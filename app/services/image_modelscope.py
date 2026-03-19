import asyncio
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

IMAGE_STYLE_PROMPTS = {
    "cartoon": "cartoon style, animated, children's book illustration, cute, whimsical",
    "watercolor": "watercolor painting, soft colors, gentle, pastel colors",
    "realistic": "realistic, photorealistic, photograph",
    "oil_painting": "oil painting style, artistic, painterly",
    "3d": "3D render, Pixar style, CGI, digital art, animated character",
    "illustration": "illustration, children's book art, whimsical, colorful"
}


class ModelScopeImageService:
    def __init__(self):
        self.api_key = os.getenv("MODELSCOPE_API_KEY", "")
        self.base_url = "https://api-inference.modelscope.cn"
        self.model = "Qwen/Qwen-Image-2512"
        self.timeout = 300
    
    async def generate_image(self, prompt: str, output_path: str, style: str = "cartoon") -> bool:
        if not self.api_key:
            logger.warning("MODELSCOPE_API_KEY not set")
            return False
        
        try:
            style_prompt = IMAGE_STYLE_PROMPTS.get(style, IMAGE_STYLE_PROMPTS["cartoon"])
            full_prompt = f"{prompt}, {style_prompt}"
            logger.info(f"Generating image with Qwen-Image-2512: {prompt[:50]}... style: {style}")
            
            async with asyncio.timeout(self.timeout):
                task_id = await self._create_task(full_prompt)
                image_url = await self._wait_for_result(task_id)
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
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true"
        }
        
        payload = {
            "model": self.model,
            "prompt": prompt
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"ModelScope API error: {response.status} - {error_text}")
                
                data = await response.json()
                return data["task_id"]
    
    async def _wait_for_result(self, task_id: str, max_wait: int = 300) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Task-Type": "image_generation"
        }
        
        url = f"{self.base_url}/v1/tasks/{task_id}"
        
        async with aiohttp.ClientSession() as session:
            for _ in range(max_wait):
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        await asyncio.sleep(5)
                        continue
                    
                    data = await response.json()
                    task_status = data.get("task_status", "PENDING")
                    
                    if task_status == "SUCCEED":
                        images = data.get("output_images", [])
                        if images:
                            return images[0]
                        raise Exception("No images in response")
                    elif task_status == "FAILED":
                        raise Exception(f"Task failed: {data.get('message', 'Unknown error')}")
                    
                    await asyncio.sleep(5)
            
            raise Exception("Generation timeout")
    
    async def _download_image(self, url: str, output_path: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image: {response.status}")
                
                content = await response.read()
                with open(output_path, "wb") as f:
                    f.write(content)
    
    async def generate_for_segments(self, segments: list[str], output_dir: str, style: str = "cartoon") -> tuple[list[str], list[dict]]:
        os.makedirs(output_dir, exist_ok=True)
        
        image_paths = []
        errors = []
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"image_{i}.png")
            try:
                success = await self.generate_image(segment, output_path, style)
                if success:
                    image_paths.append(output_path)
                else:
                    logger.warning(f"Failed to generate image for segment {i}")
                    errors.append({"segment": i, "error": "生成失败"})
            except Exception as e:
                logger.error(f"Error generating image for segment {i}: {e}")
                errors.append({"segment": i, "error": str(e)})
        return image_paths, errors