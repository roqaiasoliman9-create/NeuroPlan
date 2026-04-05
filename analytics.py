from typing import List, Dict
from models import ProgressRecord, Subject, Chapter


def calculate_completion_rate(progress_records: List[ProgressRecord]) -> float:
    if not progress_records:
        return 0.0

    total_planned = sum(r.planned_hours for r in progress_records)
    total_completed = sum(r.completed_hours for r in progress_records)

    if total_planned == 0:
        return 0.0

    return round((total_completed / total_planned) * 100, 2)


def subject_completion_summary(progress_records: List[ProgressRecord]) -> Dict[str, dict]:
    summary = {}
    for r in progress_records:
        if r.subject not in summary:
            summary[r.subject] = {
                "planned": 0.0,
                "completed": 0.0,
                "sessions": 0
            }

        summary[r.subject]["planned"] += r.planned_hours
        summary[r.subject]["completed"] += r.completed_hours
        summary[r.subject]["sessions"] += 1

    for subject, data in summary.items():
        planned = data["planned"]
        completed = data["completed"]
        data["completion_rate"] = round((completed / planned) * 100, 2) if planned else 0.0

    return summary


def readiness_score(subject: Subject, chapters: List[Chapter], progress_records: List[ProgressRecord]) -> float:
    subject_chapters = [c for c in chapters if c.subject_id == subject.id]
    if not subject_chapters:
        return 0.0

    done_count = sum(1 for c in subject_chapters if c.status == "done")
    in_progress_count = sum(1 for c in subject_chapters if c.status == "in_progress")

    coverage = ((done_count + (in_progress_count * 0.5)) / len(subject_chapters)) * 100

    related_progress = [p for p in progress_records if p.subject == subject.name]
    planned = sum(r.planned_hours for r in related_progress)
    completed = sum(r.completed_hours for r in related_progress)
    completion_rate = (completed / planned) * 100 if planned else 0

    score = (coverage * 0.55) + (completion_rate * 0.45)
    return round(min(score, 100), 2)


def chapter_status_distribution(chapters: List[Chapter]) -> dict:
    distribution = {
        "not_started": 0,
        "in_progress": 0,
        "done": 0
    }

    for chapter in chapters:
        if chapter.status in distribution:
            distribution[chapter.status] += 1

    return distribution