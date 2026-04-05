def generate_quiz_from_text(text: str, num_questions: int = 5):
    cleaned_lines = [line.strip() for line in text.split("\n") if line.strip()]
    questions = []

    for i, line in enumerate(cleaned_lines[:num_questions], start=1):
        short_line = line[:140]
        questions.append({
            "question": f"What is the main idea of: \"{short_line}\"?",
            "answer_hint": "Identify the core concept or definition."
        })

    if not questions:
        questions.append({
            "question": "Not enough content to generate quiz questions.",
            "answer_hint": "Upload a PDF with more text."
        })

    return questions