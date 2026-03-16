import asyncio
import os
import logging
import aiohttp
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class MiniMaxTTSService:
    def __init__(self):
        self.access_token = os.getenv("MINIMAX_ACCESS_TOKEN", "")
        self.model = os.getenv("MINIMAX_MODEL", "speech-02-turbo")
        self.voice = os.getenv("MINIMAX_VOICE", "male-qn-qingse")
        self.api_url = "https://api.minimax.io/v1/t2a_v2"
        self.timeout = 120
    
    @async_retry(max_attempts=3, base_delay=2)
    async def text_to_speech(self, text: str, output_path: str) -> bool:
        if not self.access_token:
            logger.warning("MINIMAX_ACCESS_TOKEN not set")
            return False
        
        try:
            logger.info(f"Generating MiniMax TTS: {text[:30]}...")
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "text": text,
                "voice_setting": {
                    "voice_id": self.voice
                },
                "audio_setting": {
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "format": "mp3"
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers, timeout=self.timeout) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"MiniMax TTS error: {resp.status} - {error}")
                        raise Exception(f"MiniMax TTS error: {resp.status}")
                    
                    audio_data = await resp.read()
                    
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
            
            logger.info(f"TTS saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"MiniMax TTS failed: {e}")
            raise
    
    async def generate_for_segments(self, segments: list[str], output_dir: str) -> list[str]:
        audio_paths = []
        for i, segment in enumerate(segments):
            output_path = os.path.join(output_dir, f"audio_{i}.mp3")
            try:
                success = await self.text_to_speech(segment, output_path)
                if success:
                    audio_paths.append(output_path)
                else:
                    logger.warning(f"Failed to generate audio for segment {i}")
            except Exception as e:
                logger.error(f"Error generating audio for segment {i}: {e}")
        return audio_paths
