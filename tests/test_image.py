from app.services.image_huggingface import ImageService

def test_image_service_init():
    service = ImageService()
    assert service is not None

def test_image_service_timeout():
    service = ImageService()
    assert service.timeout == 120
