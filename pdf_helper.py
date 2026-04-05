import PyPDF2


def extract_text_from_pdf(uploaded_file) -> str:
    text = ""
    reader = PyPDF2.PdfReader(uploaded_file)
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()


def simple_summarize_text(text: str, max_sentences: int = 6) -> str:
    if not text.strip():
        return "No text extracted from PDF."

    cleaned = text.replace("\n", " ").strip()
    sentences = [s.strip() for s in cleaned.split(".") if s.strip()]
    if not sentences:
        return cleaned[:600]

    return ". ".join(sentences[:max_sentences]) + "."


def extract_keywords(text: str, max_keywords: int = 12) -> list[str]:
    if not text.strip():
        return []

    words = text.lower().replace("\n", " ").split()
    stop_words = {
        "the", "and", "is", "in", "to", "of", "a", "for", "on", "that", "with",
        "as", "are", "was", "were", "be", "by", "an", "or", "this", "it"
    }

    freq = {}
    for word in words:
        clean = "".join(ch for ch in word if ch.isalnum())
        if len(clean) > 3 and clean not in stop_words:
            freq[clean] = freq.get(clean, 0) + 1

    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_words[:max_keywords]]