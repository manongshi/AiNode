import re


def split_text(text: str, max_chars: int = 6500, overlap_chars: int = 240) -> list[str]:
    """按段落和句子边界切分，尽量避免从句子中间截断。"""
    normalized = text.strip()
    if not normalized:
        return []
    if len(normalized) <= max_chars:
        return [normalized]

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized) if part.strip()]
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
            current = ""

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) <= max_chars:
                current = candidate
                continue
            previous = current[-overlap_chars:] if current else ""
            flush()
            current = f"{previous}\n\n{paragraph}".strip() if previous else paragraph
            continue

        sentences = [part.strip() for part in re.split(r"(?<=[。！？!?；;])\s*", paragraph) if part.strip()]
        for sentence in sentences:
            if len(sentence) > max_chars:
                for start in range(0, len(sentence), max_chars - overlap_chars):
                    piece = sentence[start : start + max_chars]
                    if piece.strip():
                        if current:
                            flush()
                        chunks.append(piece.strip())
                continue
            candidate = f"{current}{sentence}" if current else sentence
            if len(candidate) <= max_chars:
                current = candidate
                continue
            previous = current[-overlap_chars:] if current else ""
            flush()
            current = f"{previous}{sentence}".strip() if previous else sentence

    flush()
    return chunks

