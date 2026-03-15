import re

def split_text(text: str, max_segments: int = 10) -> list[str]:
    sentences = re.split(r'([。！？\n]+)', text)
    result = []
    current = ""
    for part in sentences:
        current += part
        if part.strip() and part.strip() in '。！？\n':
            result.append(current.strip())
            current = ""
    if current.strip():
        result.append(current.strip())
    return result[:max_segments]

def split_text_by_length(text: str, max_length: int = 200) -> list[str]:
    if len(text) <= max_length:
        return [text]
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]
