import asyncio
import os
import logging
import aiohttp

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

IMAGE_STYLE_PROMPTS = {
    "cartoon": "cartoon style, animated, children's book illustration, cute, whimsical",
    "watercolor": "watercolor painting, soft colors, gentle, pastel colors",
    "realistic": "realistic, photorealistic, photograph",
    "oil_painting": "oil painting style, artistic, painterly",
    "3d": "3D render, Pixar style, CGI, digital art, animated character",
    "illustration": "illustration, children's book art, whimsical, colorful"
}

class LeonardoImageService:
    def __init__(self):
        self.api_key = os.getenv("LEONARDO_API_KEY", "")
        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.model_id = os.getenv("LEONARDO_MODEL_ID", "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3")
        self.width = 1280
        self.height = 720
        self.timeout = 300
    
    @async_retry(max_attempts=3, base_delay=5)
    async def generate_image(self, prompt: str, output_path: str, style: str = "cartoon") -> bool:
        try:
            style_prompt = IMAGE_STYLE_PROMPTS.get(style, IMAGE_STYLE_PROMPTS["cartoon"])
            full_prompt = f"{prompt}, {style_prompt}"
            logger.info(f"Generating image with Leonardo: {prompt[:50]}... style: {style}")
            
            generation_id = await self._create_generation(prompt)
            
            await self._wait_for_generation(generation_id)
            
            image_url = await self._get_image_url(generation_id)
            
            await self._download_image(image_url, output_path)
            
            logger.info(f"Image saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Leonardo image generation failed: {e}")
            raise
    
    async def _create_generation(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "modelId": self.model_id,
            "width": self.width,
            "height": self.height,
            "num_images": 1,
            "alchemy": True,
            "guidanceScale": 7,
            "inferenceSteps": 28
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/generations",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Leonardo API error: {response.status} - {error_text}")
                
                data = await response.json()
                return data["generationId"]
    
    async def _wait_for_generation(self, generation_id: str, max_wait: int = 300) -> None:
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            for _ in range(max_wait):
                async with session.get(
                    f"{self.base_url}/generations/{generation_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        await asyncio.sleep(2)
                        continue
                    
                    data = await response.json()
                    status = data.get("generations_by_pk", {}).get("status", "PENDING")
                    
                    if status == "COMPLETE":
                        return
                    elif status in ["FAILED", "CANCELLED"]:
                        raise Exception(f"Generation {status.lower()}")
                    
                    await asyncio.sleep(3)
            
            raise Exception("Generation timeout")
    
    async def _get_image_url(self, generation_id: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/generations/{generation_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                data = await response.json()
                images = data.get("generations_by_pk", {}).get("generated_images", [])
                if not images:
                    raise Exception("No images generated")
                return images[0]["url"]
    
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
