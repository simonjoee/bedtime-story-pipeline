import subprocess
import os
import logging

logger = logging.getLogger(__name__)

class VideoService:
    def __init__(self):
        self.resolution = "1280x720"
        self.fps = 30
        self.transition = "fade"
    
    def check_ffmpeg(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except Exception:
            return False
    
    def synthesize(self, image_paths: list[str], audio_paths: list[str], output_path: str) -> bool:
        if not image_paths or not audio_paths:
            logger.error("No images or audio to synthesize")
            return False
        
        if not self.check_ffmpeg():
            logger.error("FFmpeg not available")
            return False
        
        demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
        
        if demo_mode:
            logger.info("Demo mode: creating placeholder video file")
            with open(output_path, 'wb') as f:
                f.write(b'DEMO_VIDEO')
            return True
        
        try:
            concat_list = []
            for i, (img, audio) in enumerate(zip(image_paths, audio_paths)):
                duration = self._get_duration(audio)
                segment = f"/tmp/segment_{i}.mp4"
                self._create_segment(img, segment, duration)
                concat_list.append(segment)
            
            self._concat_segments(concat_list, output_path)
            
            for seg in concat_list:
                if os.path.exists(seg):
                    os.remove(seg)
            
            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"Video synthesis failed: {e}")
            return False
    
    def _get_duration(self, audio_path: str) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-i", audio_path, "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1"],
                capture_output=True, text=True, check=True
            )
            return float(result.stdout.strip())
        except Exception:
            return 3.0
    
    def _create_segment(self, image_path: str, output_path: str, duration: float):
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-c:v", "libx264", "-t", str(duration),
            "-vf", f"scale={self.resolution}",
            "-pix_fmt", "yuv420p", output_path
        ], capture_output=True)
    
    def _concat_segments(self, segments: list[str], output_path: str):
        list_file = "/tmp/concat_list.txt"
        with open(list_file, 'w') as f:
            for seg in segments:
                f.write(f"file '{seg}'\n")
        
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
            "-c", "copy", output_path
        ], capture_output=True)
        
        os.remove(list_file)
