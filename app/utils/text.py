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

def split_text_by_duration(
    text: str,
    target_duration: float = 30.0,
    avg_chars_per_second: float = 4.0
) -> list[str]:
    if not text or not text.strip():
        return []
    
    max_chars_per_segment = int(target_duration * avg_chars_per_second)
    
    sentences = re.split(r'([。！？\n]+)', text)
    segments = []
    current_segment = ""
    
    for part in sentences:
        current_segment += part
        
        if part.strip() and part.strip() in '。！？\n':
            if len(current_segment) >= max_chars_per_segment:
                if current_segment.strip():
                    segments.append(current_segment.strip())
                current_segment = ""
        elif len(current_segment) >= max_chars_per_segment:
            if current_segment.strip():
                segments.append(current_segment.strip())
            current_segment = ""
    
    if current_segment.strip():
        segments.append(current_segment.strip())
    
    if not segments:
        segments = [text]
    
    return segments
