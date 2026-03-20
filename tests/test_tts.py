from app.services.tts_minimax import MiniMaxTTSService

def test_tts_minimax_service_init():
    service = MiniMaxTTSService()
    assert service is not None
