import asyncio
import os
import logging
import edge_tts

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.voice = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")
        self.rate = os.getenv("TTS_RATE", "-10%")
        self.pitch = os.getenv("TTS_PITCH", "-10Hz")
    
    @async_retry(max_attempts=3, base_delay=2)
    async def text_to_speech(self, text: str, output_path: str) -> bool:
        try:
            logger.info(f"Generating TTS: {text[:30]}...")
            
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            await communicate.save(output_path)
            
            logger.info(f"TTS saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"TTS failed: {e}")
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
