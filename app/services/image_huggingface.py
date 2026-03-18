import asyncio
import os
import logging
from PIL import Image
from huggingface_hub import InferenceClient

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

IMAGE_STYLE_PROMPTS = {
    "cartoon": "cartoon style, animated, children's book illustration, cute, whimsical, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind",
    "watercolor": "watercolor painting, soft colors, gentle, pastel colors, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind",
    "realistic": "realistic, photorealistic, photograph, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind",
    "oil_painting": "oil painting style, artistic, painterly, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind",
    "3d": "3D render, Pixar style, CGI, digital art, animated character, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind",
    "illustration": "illustration, children's book art, whimsical, colorful, pure visual storytelling, absolutely no text, no words, no letters, no numbers, no signage, no labels, no captions, no writing of any kind"
}

class ImageService:
    def __init__(self):
        self.api_key = os.getenv("HF_API_KEY", "")
        self.model = os.getenv("IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
        self.timeout = 180
    
    @async_retry(max_attempts=3, base_delay=5)
    async def generate_image(self, prompt: str, output_path: str, style: str = "cartoon") -> bool:
        try:
            style_prompt = IMAGE_STYLE_PROMPTS.get(style, IMAGE_STYLE_PROMPTS["cartoon"])
            full_prompt = f"{prompt}, {style_prompt}"
            logger.info(f"Generating image: {prompt[:50]}... style: {style}")
            
            def generate():
                client = InferenceClient(self.model, token=self.api_key)
                image = client.text_to_image(full_prompt, width=1280, height=720)
                return image
            
            image = await asyncio.to_thread(generate)
            
            image.save(output_path)
            logger.info(f"Image saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            raise
    
    async def generate_for_segments(self, segments: list[str], output_dir: str, style: str = "cartoon") -> tuple[list[str], list[dict]]:
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
