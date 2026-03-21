import pytest
from unittest.mock import AsyncMock, patch
from app.services.book_summary import BookSummaryService, BOOK_SUMMARY_PROMPT


@pytest.fixture
def book_summary_service():
    return BookSummaryService()


@pytest.mark.asyncio
async def test_book_summary_service_fallback():
    service = BookSummaryService()
    result = await service.generate_summary("小王子")

    assert "book_name" in result
    assert "summary" in result
    assert result["book_name"] == "小王子"
    assert len(result["summary"]) > 0


@pytest.mark.asyncio
async def test_book_summary_service_no_api_key():
    with patch.dict('os.environ', {'ZHIPU_API_KEY': ''}):
        service = BookSummaryService()
        result = await service.generate_summary("小王子")

        assert result["book_name"] == "小王子"
        assert "从前" in result["summary"]


def test_book_summary_prompt_exists():
    assert len(BOOK_SUMMARY_PROMPT) > 0
    assert "睡前" in BOOK_SUMMARY_PROMPT