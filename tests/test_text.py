from app.utils.text import split_text, split_text_by_duration

def test_split_text_by_sentences():
    text = "从前有座山。山上有座庙。庙里有个老和尚。"
    result = split_text(text)
    assert len(result) == 3
    assert result[0] == "从前有座山。"

def test_split_text_max_segments():
    text = "第一句。第二句。第三句。第四句。第五句。第六句。第七句。第八句。第九句。第十句。第十一句。"
    result = split_text(text, max_segments=10)
    assert len(result) == 10

def test_split_text_by_duration_short_text():
    text = "从前有座山。"
    result = split_text_by_duration(text, target_duration=30, avg_chars_per_second=4)
    assert len(result) == 1

def test_split_text_by_duration_long_text():
    text = "从前有座山。山上有座庙。庙里有个老和尚。老和尚给小和尚讲故事。故事的名字叫《从前有座山》。这是一个循环的故事，永远讲不完。有一天，小和尚问老和尚：师傅，这个故事什么时候结束？老和尚笑着说：永远不会结束，因为这就是《从前有座山》。小和尚想了想又说：可是师傅，我想听新的故事。老和尚点点头说好，于是开始讲第二个故事。从前有只小兔子，它住在森林里。"
    result = split_text_by_duration(text, target_duration=30, avg_chars_per_second=4)
    assert len(result) >= 2
