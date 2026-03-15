import aiohttp
import asyncio
import os
import logging

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class ImageService:
    def __init__(self):
        self.api_key = os.getenv("IMAGE_API_KEY", "")
        self.api_endpoint = os.getenv("IMAGE_ENDPOINT", "")
        self.provider = os.getenv("IMAGE_PROVIDER", "leonardo")
        self.timeout = 120
    
    @async_retry(max_attempts=3, base_delay=2)
    async def generate_image(self, prompt: str, output_path: str) -> bool:
        try:
            logger.info(f"Image: {prompt[:50]}... -> {output_path}")
            await asyncio.sleep(0.5)
            
            with open(output_path, 'wb') as f:
                f.write(b'\x89PNG')
            return True
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise
    
    async def generate_for_segments(self, segments: list[str], output_dir: str) -> list[str]:
        image_paths = []
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"image_{i}.png")
            success = await self.generate_image(segment, output_path)
            if success:
                image_paths.append(output_path)
            else:
                logger.warning(f"Failed to generate image for segment {i}")
        return image_paths
