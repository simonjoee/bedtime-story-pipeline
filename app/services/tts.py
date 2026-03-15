import aiohttp
import asyncio
import os
import logging
import base64

from app.utils.retry import async_retry

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.api_key = os.getenv("TTS_API_KEY", "")
        self.api_endpoint = os.getenv("TTS_ENDPOINT", "https://eastus.api.cognitive.microsoft.com")
        self.voice = os.getenv("TTS_VOICE", "zh-CN-YunxiNeural")
        self.timeout = 60
    
    @async_retry(max_attempts=3, base_delay=2)
    async def text_to_speech(self, text: str, output_path: str) -> bool:
        if not self.api_key:
            logger.warning("TTS_API_KEY not set, using demo mode")
            await asyncio.sleep(0.5)
            with open(output_path, 'wb') as f:
                f.write(b'RIFF')
            return True
        
        try:
            url = f"{self.api_endpoint}/tts/cognitiveservices/v1"
            headers = {
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm"
            }
            
            ssml = f"""
            <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
                <voice name='{self.voice}'>
                    <prosody rate='-10%' pitch='-10%'>
                        {text}
                    </prosody>
                </voice>
            </speak>
            """
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=ssml.encode('utf-8'), timeout=self.timeout) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        logger.error(f"TTS API error: {resp.status} - {error}")
                        raise Exception(f"TTS API error: {resp.status}")
                    
                    audio_data = await resp.read()
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
            
            logger.info(f"TTS generated: {text[:30]}... -> {output_path}")
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
