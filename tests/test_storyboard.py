import pytest
from unittest.mock import AsyncMock, patch
from app.services.storyboard import StoryboardService
from app.models import Segment


@pytest.fixture
def storyboard_service():
    return StoryboardService()


@pytest.mark.asyncio
async def test_storyboard_service_fallback():
    story = "从前有一只小兔子，它住在森林里。"
    
    service = StoryboardService()
    result = await service.generate(story)
    
    assert len(result) == 1
    assert result[0]["text"] == story
    assert "image_prompt" in result[0]


@pytest.mark.asyncio
async def test_storyboard_service_no_api_key():
    with patch.dict('os.environ', {'ZHIPU_API_KEY': ''}):
        service = StoryboardService()
        result = await service.generate("test story")
        
        assert len(result) == 1
        assert "image_prompt" in result[0]


def test_segment_model():
    segment = Segment(text="test", image_prompt="test prompt")
    assert segment.text == "test"
    assert segment.image_prompt == "test prompt"
    assert segment.image_path is None


def test_segment_model_dump():
    segment = Segment(text="test", image_prompt="test prompt")
    data = segment.model_dump()
    
    assert data["text"] == "test"
    assert data["image_prompt"] == "test prompt"
