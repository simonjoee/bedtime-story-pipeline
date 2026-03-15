import aiohttp
import asyncio
import os
import logging

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.api_key = os.getenv("TTS_API_KEY", "")
        self.api_endpoint = os.getenv("TTS_ENDPOINT", "")
        self.provider = os.getenv("TTS_PROVIDER", "azure")
        self.timeout = 60
    
    @async_retry(max_attempts=3, base_delay=2)
    async def text_to_speech(self, text: str, output_path: str) -> bool:
        try:
            logger.info(f"TTS: {text[:50]}... -> {output_path}")
            await asyncio.sleep(0.5)
            
            with open(output_path, 'wb') as f:
                f.write(b'RIFF')
            return True
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise
    
    async def generate_for_segments(self, segments: list[str], output_dir: str) -> list[str]:
        audio_paths = []
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"audio_{i}.wav")
            success = await self.text_to_speech(segment, output_path)
            if success:
                audio_paths.append(output_path)
            else:
                logger.warning(f"Failed to generate audio for segment {i}")
        return audio_paths
