from datetime import datetime, date, timedelta
from typing import List, Dict
from models import Subject, Chapter, ProgressRecord


def today_date() -> date:
    return datetime.today().date()


def days_until_exam(exam_date: str) -> int:
    exam = datetime.strptime(exam_date, "%Y-%m-%d").date()
    diff = (exam - today_date()).days
    return max(diff, 1)


def level_score(level: str) -> int:
    return {"weak": 3, "medium": 2, "good": 1}.get(level.lower(), 1)


def difficulty_score(difficulty: str) -> int:
    return {"easy": 1, "medium": 2, "hard": 3}.get(difficulty.lower(), 1)


def subject_type_score(subject_type: str) -> float:
    return {
        "problem_solving": 1.3,
        "memory_heavy": 1.15,
        "reading_heavy": 1.0,
        "mixed": 1.2
    }.get(subject_type.lower(), 1.0)


def chapter_recent_penalty(subject_name: str, chapter_name: str, progress_records: List[ProgressRecord]) -> float:
    penalty = 0.0
    for record in progress_records[:12]:
        if record.subject == subject_name and record.chapter == chapter_name:
            if record.status == "skipped":
                penalty += 1.2
            elif record.status == "partial":
                penalty += 0.6
    return penalty


def chapter_priority(subject: Subject, chapter: Chapter, progress_records: List[ProgressRecord]) -> float:
    days_left = days_until_exam(subject.exam_date)

    weak_bonus = 1.5 if chapter.weak == 1 else 0.0
    status_bonus = {
        "not_started": 1.2,
        "in_progress": 1.6,
        "done": -3.0
    }.get(chapter.status, 0.0)

    progress_penalty = chapter_recent_penalty(subject.name, chapter.name, progress_records)

    score = (
        (14 / days_left) * 0.28 +
        level_score(subject.level) * 0.14 +
        difficulty_score(subject.difficulty) * 0.12 +
        difficulty_score(chapter.difficulty) * 0.16 +
        subject_type_score(subject.subject_type) * 0.10 +
        subject.preferred_hours * 0.05 +
        weak_bonus +
        status_bonus +
        progress_penalty
    )

    return round(max(score, 0.1), 2)


def recommend_study_type(subject: Subject, days_left: int, chapter: Chapter) -> str:
    if chapter.status == "done":
        return "Revision"

    if days_left <= 2:
        return "Mock Test" if subject.subject_type == "problem_solving" else "Revision"

    if days_left <= 5:
        return "Practice" if subject.subject_type == "problem_solving" else "Revision"

    if chapter.weak == 1:
        return "Practice" if subject.subject_type == "problem_solving" else "Study"

    if chapter.status == "in_progress":
        return "Revision" if subject.subject_type != "problem_solving" else "Practice"

    return "Study"


def round_to_half_hour(value: float) -> float:
    return round(value * 2) / 2


def next_revision_date(study_type: str) -> str | None:
    base = today_date()
    if study_type == "Study":
        return str(base + timedelta(days=1))
    if study_type == "Practice":
        return str(base + timedelta(days=2))
    if study_type == "Revision":
        return str(base + timedelta(days=3))
    if study_type == "Mock Test":
        return str(base + timedelta(days=1))
    return None


def reminder_note(days_left: int, study_type: str) -> str:
    if days_left <= 2:
        return "High urgency. Focus on active recall and exam-style review."
    if study_type == "Mock Test":
        return "Do the session under timed conditions."
    if study_type == "Revision":
        return "Review errors, summaries, and key concepts."
    if study_type == "Practice":
        return "Prioritize problem-solving and correction."
    return "Start with understanding, then summarize the chapter."


def build_plan(
    subjects: List[Subject],
    chapters: List[Chapter],
    daily_hours: float,
    progress_records: List[ProgressRecord]
) -> List[dict]:
    if not subjects or not chapters or daily_hours <= 0:
        return []

    subject_map = {s.id: s for s in subjects}
    raw_tasks = []

    for chapter in chapters:
        subject = subject_map.get(chapter.subject_id)
        if not subject or chapter.status == "done":
            continue

        priority = chapter_priority(subject, chapter, progress_records)
        days_left = days_until_exam(subject.exam_date)
        study_type = recommend_study_type(subject, days_left, chapter)

        raw_tasks.append({
            "subject": subject.name,
            "chapter": chapter.name,
            "priority": priority,
            "days_left": days_left,
            "study_type": study_type,
            "revision_date": next_revision_date(study_type),
            "reminder_note": reminder_note(days_left, study_type)
        })

    raw_tasks.sort(key=lambda x: x["priority"], reverse=True)

    max_tasks = 3 if daily_hours <= 3 else 5
    selected = raw_tasks[:max_tasks]

    if not selected:
        return []

    total_priority = sum(x["priority"] for x in selected)

    final_plan = []
    for item in selected:
        hours = (item["priority"] / total_priority) * daily_hours
        hours = max(0.5, min(3.0, round_to_half_hour(hours)))

        final_plan.append({
            **item,
            "hours": hours
        })

    # adjust total
    current_total = sum(x["hours"] for x in final_plan)
    difference = round(current_total - daily_hours, 2)

    if difference > 0:
        for item in sorted(final_plan, key=lambda x: x["priority"]):
            while difference > 0 and item["hours"] > 0.5:
                item["hours"] -= 0.5
                difference = round(difference - 0.5, 2)
    elif difference < 0:
        difference = abs(difference)
        for item in sorted(final_plan, key=lambda x: x["priority"], reverse=True):
            while difference > 0 and item["hours"] < 3.0:
                item["hours"] += 0.5
                difference = round(difference - 0.5, 2)

    final_plan.sort(key=lambda x: x["priority"], reverse=True)
    return final_plan


def generate_weekly_plan(
    subjects: List[Subject],
    chapters: List[Chapter],
    daily_hours: float,
    progress_records: List[ProgressRecord]
) -> Dict[str, List[dict]]:
    base = today_date()
    plan = {}
    for i in range(7):
        current_day = base + timedelta(days=i)
        plan[str(current_day)] = build_plan(subjects, chapters, daily_hours, progress_records)
    return plan


def build_session_blocks(tasks: List[dict], break_minutes: int = 10) -> List[dict]:
    rows = []
    current_start_hour = 9
    current_start_minute = 0

    for task in tasks:
        total_minutes = int(task["hours"] * 60)
        remaining = total_minutes
        block_num = 1

        while remaining > 0:
            block_minutes = 50 if remaining > 50 else remaining

            start_text = f"{current_start_hour:02d}:{current_start_minute:02d}"
            end_total = current_start_hour * 60 + current_start_minute + block_minutes
            end_hour = end_total // 60
            end_minute = end_total % 60
            end_text = f"{end_hour:02d}:{end_minute:02d}"

            rows.append({
                "subject": task["subject"],
                "chapter": task["chapter"],
                "study_type": task["study_type"],
                "session": f"Block {block_num}",
                "start": start_text,
                "end": end_text,
                "focus_minutes": block_minutes,
                "break_after": break_minutes if remaining > block_minutes else 0
            })

            current_start_hour = end_hour
            current_start_minute = end_minute + (break_minutes if remaining > block_minutes else 0)

            if current_start_minute >= 60:
                current_start_hour += current_start_minute // 60
                current_start_minute = current_start_minute % 60

            remaining -= block_minutes
            block_num += 1

    return rows