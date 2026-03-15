from app.services.video import VideoService

def test_video_service_init():
    service = VideoService()
    assert service is not None

def test_video_service_defaults():
    service = VideoService()
    assert service.resolution == "1280x720"
    assert service.fps == 30
