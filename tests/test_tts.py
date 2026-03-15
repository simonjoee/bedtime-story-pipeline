from app.services.tts import TTSService

def test_tts_service_init():
    service = TTSService()
    assert service is not None

def test_tts_service_timeout():
    service = TTSService()
    assert service.timeout == 60
