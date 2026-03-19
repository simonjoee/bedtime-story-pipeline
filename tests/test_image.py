from app.services.image_modelscope import ModelScopeImageService


def test_image_service_init():
    service = ModelScopeImageService()
    assert service is not None


def test_image_service_config():
    service = ModelScopeImageService()
    assert service.model == "Qwen/Qwen-Image-2512"
    assert service.base_url == "https://api-inference.modelscope.cn"