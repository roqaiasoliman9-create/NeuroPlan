import sqlite3
from typing import List, Optional
from models import User, Classroom, Subject, Chapter, ProgressRecord, Notification
import os

DB_NAME = os.path.join("data", "study_planner_v8.db")

DB_NAME = "data/study_planner_v8.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


# =========================
# Users
# =========================

def create_user(full_name: str, email: str, password_hash: str, role: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (full_name, email, password_hash, role)
        VALUES (?, ?, ?, ?)
    """, (full_name, email, password_hash, role))
    user_id = cursor.lastrowid
    cursor.execute("""
        INSERT OR IGNORE INTO settings (user_id, daily_hours, break_minutes)
        VALUES (?, 4.0, 10)
    """, (user_id,))
    conn.commit()
    conn.close()


def find_user_by_email(email: str) -> Optional[User]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, full_name, email, password_hash, role
        FROM users
        WHERE email = ?
    """, (email,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return User(
        id=row[0],
        full_name=row[1],
        email=row[2],
        password_hash=row[3],
        role=row[4]
    )


def get_user_by_id(user_id: int) -> Optional[User]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, full_name, email, password_hash, role
        FROM users
        WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return User(*row)


def load_users(role: Optional[str] = None) -> List[User]:
    conn = get_connection()
    cursor = conn.cursor()

    if role:
        cursor.execute("""
            SELECT id, full_name, email, password_hash, role
            FROM users
            WHERE role = ?
            ORDER BY full_name
        """, (role,))
    else:
        cursor.execute("""
            SELECT id, full_name, email, password_hash, role
            FROM users
            ORDER BY role, full_name
        """)

    rows = cursor.fetchall()
    conn.close()

    return [User(*row) for row in rows]


# =========================
# Classrooms
# =========================

def create_classroom(name: str, teacher_id: Optional[int]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO classrooms (name, teacher_id)
        VALUES (?, ?)
    """, (name, teacher_id))
    conn.commit()
    conn.close()


def load_classrooms() -> List[Classroom]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, teacher_id
        FROM classrooms
        ORDER BY name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [Classroom(*row) for row in rows]


def assign_student_to_class(class_id: int, student_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*)
        FROM class_students
        WHERE class_id = ? AND student_id = ?
    """, (class_id, student_id))
    exists = cursor.fetchone()[0]

    if exists == 0:
        cursor.execute("""
            INSERT INTO class_students (class_id, student_id)
            VALUES (?, ?)
        """, (class_id, student_id))
    conn.commit()
    conn.close()


def get_students_in_class(class_id: int) -> List[User]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.full_name, u.email, u.password_hash, u.role
        FROM users u
        INNER JOIN class_students cs ON u.id = cs.student_id
        WHERE cs.class_id = ?
        ORDER BY u.full_name
    """, (class_id,))
    rows = cursor.fetchall()
    conn.close()
    return [User(*row) for row in rows]


def get_classes_for_student(student_id: int) -> List[Classroom]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.teacher_id
        FROM classrooms c
        INNER JOIN class_students cs ON c.id = cs.class_id
        WHERE cs.student_id = ?
        ORDER BY c.name
    """, (student_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Classroom(*row) for row in rows]


def get_classes_for_teacher(teacher_id: int) -> List[Classroom]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, teacher_id
        FROM classrooms
        WHERE teacher_id = ?
        ORDER BY name
    """, (teacher_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Classroom(*row) for row in rows]


# =========================
# Subjects
# =========================

def add_subject(subject: Subject):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO subjects (
            user_id, class_id, name, exam_date, level, difficulty, units, subject_type, preferred_hours
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        subject.user_id, subject.class_id, subject.name, subject.exam_date,
        subject.level, subject.difficulty, subject.units,
        subject.subject_type, subject.preferred_hours
    ))
    conn.commit()
    conn.close()


def load_subjects_for_user(user_id: int) -> List[Subject]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, class_id, name, exam_date, level, difficulty, units, subject_type, preferred_hours
        FROM subjects
        WHERE user_id = ?
        ORDER BY exam_date ASC, name ASC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Subject(*row) for row in rows]


def delete_subject(subject_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chapters WHERE subject_id = ?", (subject_id,))
    cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()


# =========================
# Chapters
# =========================

def add_chapter(chapter: Chapter):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO chapters (subject_id, name, difficulty, status, weak)
        VALUES (?, ?, ?, ?, ?)
    """, (chapter.subject_id, chapter.name, chapter.difficulty, chapter.status, chapter.weak))
    conn.commit()
    conn.close()


def load_chapters_for_subject(subject_id: int) -> List[Chapter]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, subject_id, name, difficulty, status, weak
        FROM chapters
        WHERE subject_id = ?
        ORDER BY name
    """, (subject_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Chapter(*row) for row in rows]


def load_chapters_for_user(user_id: int) -> List[Chapter]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.subject_id, c.name, c.difficulty, c.status, c.weak
        FROM chapters c
        INNER JOIN subjects s ON c.subject_id = s.id
        WHERE s.user_id = ?
        ORDER BY c.name
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Chapter(*row) for row in rows]


def update_chapter(chapter_id: int, name: str, difficulty: str, status: str, weak: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE chapters
        SET name = ?, difficulty = ?, status = ?, weak = ?
        WHERE id = ?
    """, (name, difficulty, status, weak, chapter_id))
    conn.commit()
    conn.close()


def delete_chapter(chapter_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
    conn.commit()
    conn.close()


# =========================
# Progress
# =========================

def add_progress(record: ProgressRecord):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO progress (user_id, date, subject, chapter, planned_hours, completed_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        record.user_id, record.date, record.subject, record.chapter,
        record.planned_hours, record.completed_hours, record.status
    ))
    conn.commit()
    conn.close()


def load_progress_for_user(user_id: int) -> List[ProgressRecord]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, date, subject, chapter, planned_hours, completed_hours, status
        FROM progress
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [ProgressRecord(*row) for row in rows]


# =========================
# Settings
# =========================

def get_user_settings(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT daily_hours, break_minutes
        FROM settings
        WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"daily_hours": 4.0, "break_minutes": 10}

    return {
        "daily_hours": row[0],
        "break_minutes": row[1]
    }


def save_user_settings(user_id: int, daily_hours: float, break_minutes: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO settings (user_id, daily_hours, break_minutes)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
        daily_hours = excluded.daily_hours,
        break_minutes = excluded.break_minutes
    """, (user_id, daily_hours, break_minutes))
    conn.commit()
    conn.close()


# =========================
# Notifications
# =========================

def create_notification(user_id: int, title: str, message: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (user_id, title, message, is_read)
        VALUES (?, ?, ?, 0)
    """, (user_id, title, message))
    conn.commit()
    conn.close()


def load_notifications(user_id: int) -> List[Notification]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, title, message, is_read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [Notification(*row) for row in rows]


def mark_notification_read(notification_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ?
    """, (notification_id,))
    conn.commit()
    conn.close()


# =========================
# Utility
# =========================

def reset_database_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM class_students")
    cursor.execute("DELETE FROM classrooms")
    cursor.execute("DELETE FROM chapters")
    cursor.execute("DELETE FROM subjects")
    cursor.execute("DELETE FROM progress")
    cursor.execute("DELETE FROM notifications")
    cursor.execute("DELETE FROM study_notes")
    cursor.execute("DELETE FROM users WHERE role != 'admin'")
    cursor.execute("DELETE FROM settings WHERE user_id NOT IN (SELECT id FROM users)")
    conn.commit()
    conn.close()