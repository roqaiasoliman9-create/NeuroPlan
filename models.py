from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class User:
    id: Optional[int]
    full_name: str
    email: str
    password_hash: str
    role: str  # admin / teacher / student

    def to_dict(self):
        return asdict(self)


@dataclass
class Classroom:
    id: Optional[int]
    name: str
    teacher_id: Optional[int]

    def to_dict(self):
        return asdict(self)


@dataclass
class Subject:
    id: Optional[int]
    user_id: int
    class_id: Optional[int]
    name: str
    exam_date: str
    level: str
    difficulty: str
    units: int
    subject_type: str
    preferred_hours: float = 1.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Chapter:
    id: Optional[int]
    subject_id: int
    name: str
    difficulty: str
    status: str = "not_started"
    weak: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class ProgressRecord:
    id: Optional[int]
    user_id: int
    date: str
    subject: str
    chapter: str
    planned_hours: float
    completed_hours: float
    status: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Notification:
    id: Optional[int]
    user_id: int
    title: str
    message: str
    is_read: int = 0
    created_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)