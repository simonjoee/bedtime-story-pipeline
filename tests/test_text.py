from app.utils.text import split_text

def test_split_text_by_sentences():
    text = "从前有座山。山上有座庙。庙里有个老和尚。"
    result = split_text(text)
    assert len(result) == 3
    assert result[0] == "从前有座山。"

def test_split_text_max_segments():
    text = "第一句。第二句。第三句。第四句。第五句。第六句。第七句。第八句。第九句。第十句。第十一句。"
    result = split_text(text, max_segments=10)
    assert len(result) == 10
