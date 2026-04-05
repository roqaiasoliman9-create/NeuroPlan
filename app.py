from datetime import datetime
import base64
from pathlib import Path

import pandas as pd
import streamlit as st

from db_init import init_db
from auth import authenticate_user, hash_password
from models import Subject, Chapter, ProgressRecord
from storage import (
    create_user,
    load_users,
    get_user_by_id,
    create_classroom,
    load_classrooms,
    assign_student_to_class,
    get_students_in_class,
    get_classes_for_teacher,
    get_classes_for_student,
    add_subject,
    load_subjects_for_user,
    delete_subject,
    add_chapter,
    load_chapters_for_subject,
    load_chapters_for_user,
    update_chapter,
    delete_chapter,
    add_progress,
    load_progress_for_user,
    get_user_settings,
    save_user_settings,
    create_notification,
    load_notifications,
    mark_notification_read,
    reset_database_data
)
from planner import build_plan, generate_weekly_plan, build_session_blocks
from analytics import (
    calculate_completion_rate,
    subject_completion_summary,
    readiness_score,
    chapter_status_distribution
)
from pdf_helper import extract_text_from_pdf, simple_summarize_text, extract_keywords
from export_helper import df_to_csv_bytes, plan_to_pdf_bytes
import random


# =========================
# Setup
# =========================

init_db()
st.set_page_config(page_title="Study Planner", layout="wide")


# =========================
# UI Helpers
# =========================

def img_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_css():
    css_file = Path("styles.css")
    if css_file.exists():
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_page_header():
    st.markdown('<div class="main-title">Study Planner</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtle-text">Soft dashboard theme with calmer study flow.</div>',
        unsafe_allow_html=True
    )


def render_hero_section(user_name: str):
    image_path = Path("assets/cartoon_student.png")

    if image_path.exists():
        image_html = f"""
        <div class="hero-illustration-wrap">
            <img src="data:image/png;base64,{img_to_base64(str(image_path))}">
        </div>
        """
    else:
        image_html = """
        <div class="hero-illustration-wrap">
            <div style="font-size:80px;">📚</div>
        </div>
        """

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-left">
                <div class="hero-chip">Let’s Start!</div>
                <div class="hero-title">Hi, {user_name}.</div>
                <div class="hero-desc">
                    Are you ready to build better study habits with a softer and smarter dashboard?
                </div>
                <div class="hero-btn">Continue</div>
            </div>
            {image_html}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_metric_pills(subjects_count, chapters_count, daily_hours, completion_rate):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="metric-pill metric-blue">
                <h4>Subjects</h4>
                <div class="metric-value">{subjects_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
            <div class="metric-pill metric-yellow">
                <h4>Chapters</h4>
                <div class="metric-value">{chapters_count}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-pill metric-pink">
                <h4>Daily Hours</h4>
                <div class="metric-value">{daily_hours}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c4:
        st.markdown(
            f"""
            <div class="metric-pill metric-mint">
                <h4>Completion</h4>
                <div class="metric-value">{completion_rate}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def task_color_class(index: int) -> str:
    colors = ["task-blue", "task-pink", "task-coral", "task-mint", "task-yellow"]
    return colors[index % len(colors)]


def render_pretty_tasks(today_plan: list[dict]):
    st.markdown('<div class="section-title">Today’s Focus</div>', unsafe_allow_html=True)

    if not today_plan:
        st.info("No study tasks available yet.")
        return

    for i, task in enumerate(today_plan):
        st.markdown(
            f"""
            <div class="task-card {task_color_class(i)}">
                <h4>{task['chapter']}</h4>
                <div class="task-meta">
                    <strong>{task['subject']}</strong> • {task['study_type']} • {task['hours']}h
                </div>
                <div class="small-muted" style="margin-top:8px;">
                    {task.get('reminder_note', '')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_reminder_box():
    st.markdown(
        """
        <div class="reminder-box">
            <strong>Gentle Reminder</strong><br>
            Focus on consistency more than intensity. A calm focused session is better than a long distracted one.
        </div>
        """,
        unsafe_allow_html=True
    )


def chapter_status_badge(status: str) -> str:
    return {
        "not_started": "🔴 Not Started",
        "in_progress": "🟡 In Progress",
        "done": "🟢 Done"
    }.get(status, status)


# =========================
# Session Helpers
# =========================

def init_session():
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "role" not in st.session_state:
        st.session_state.role = None
    if "full_name" not in st.session_state:
        st.session_state.full_name = None


def login_user(user):
    st.session_state.user_id = user.id
    st.session_state.role = user.role
    st.session_state.full_name = user.full_name


def logout_user():
    st.session_state.user_id = None
    st.session_state.role = None
    st.session_state.full_name = None


def require_login():
    return st.session_state.user_id is not None

def get_smart_sidebar_message(subjects, chapters, progress_records, role):
    if role == "admin":
        return {
            "title": "System Focus",
            "text": "Monitor growth, keep the structure clean, and maintain a clear overview of users and classes."
        }

    if role == "teacher":
        return {
            "title": "Teaching Focus",
            "text": "Keep your classes organized and support students with steady follow-up, not just last-minute checks."
        }

    if not subjects:
        return {
            "title": "Start Here",
            "text": "Add your first subject and build a study plan one step at a time."
        }

    if not chapters:
        return {
            "title": "Next Step",
            "text": "Your subjects are ready. Add chapters now to generate a more useful study plan."
        }

    weak_chapters = sum(1 for ch in chapters if ch.weak == 1)
    done_chapters = sum(1 for ch in chapters if ch.status == "done")
    total_chapters = len(chapters)

    completion_rate = calculate_completion_rate(progress_records)

    if weak_chapters >= 3:
        return {
            "title": "Priority",
            "text": "You have several weak chapters. Review them first before adding more new material."
        }

    if total_chapters > 0 and done_chapters == total_chapters:
        return {
            "title": "Excellent",
            "text": "You completed all current chapters. Shift your focus to revision and mock-test practice."
        }

    if completion_rate >= 75:
        return {
            "title": "Strong Progress",
            "text": "You are doing well. Keep your rhythm steady and protect your consistency."
        }

    if completion_rate >= 40:
        return {
            "title": "Keep Going",
            "text": "Your momentum is building. Focus on finishing in-progress chapters before starting new ones."
        }

    if progress_records:
        return {
            "title": "Refocus",
            "text": "Your progress is still early. Make today simple: one hard task, one easy win, then stop."
        }

    return {
        "title": "Daily Focus",
        "text": "Start small and stay consistent. A focused session today is better than a perfect plan tomorrow."
    }


init_session()
load_css()

def get_smart_sidebar_message(subjects, chapters, progress_records, role):
    if role == "admin":
        return {
            "title": "System Focus",
            "text": "Monitor growth, keep the structure clean, and maintain a clear overview of users and classes."
        }

    if role == "teacher":
        return {
            "title": "Teaching Focus",
            "text": "Keep your classes organized and support students with steady follow-up, not just last-minute checks."
        }

    if not subjects:
        return {
            "title": "Start Here",
            "text": "Add your first subject and build a study plan one step at a time."
        }

    if not chapters:
        return {
            "title": "Next Step",
            "text": "Your subjects are ready. Add chapters now to generate a more useful study plan."
        }

    weak_chapters = sum(1 for ch in chapters if ch.weak == 1)
    done_chapters = sum(1 for ch in chapters if ch.status == "done")
    total_chapters = len(chapters)

    completion_rate = calculate_completion_rate(progress_records)

    if weak_chapters >= 3:
        return {
            "title": "Priority",
            "text": "You have several weak chapters. Review them first before adding more new material."
        }

    if total_chapters > 0 and done_chapters == total_chapters:
        return {
            "title": "Excellent",
            "text": "You completed all current chapters. Shift your focus to revision and mock-test practice."
        }

    if completion_rate >= 75:
        return {
            "title": "Strong Progress",
            "text": "You are doing well. Keep your rhythm steady and protect your consistency."
        }

    if completion_rate >= 40:
        return {
            "title": "Keep Going",
            "text": "Your momentum is building. Focus on finishing in-progress chapters before starting new ones."
        }

    if progress_records:
        return {
            "title": "Refocus",
            "text": "Your progress is still early. Make today simple: one hard task, one easy win, then stop."
        }

    return {
        "title": "Daily Focus",
        "text": "Start small and stay consistent. A focused session today is better than a perfect plan tomorrow."
    }





# =========================
# Auth Screen
# =========================

if not require_login():
    render_page_header()

    st.markdown(
        """
        <div class="soft-card" style="max-width:760px; margin-top:18px;">
            <div class="section-title">Welcome Back</div>
            <div class="small-muted" style="margin-bottom:16px;">
                Log in to continue your study journey or create a new account.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])

    with auth_tab1:
        st.markdown('<div class="section-title">Login</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login")

            if submit_login:
                user = authenticate_user(email.strip(), password)
                if user:
                    login_user(user)
                    st.success("Logged in successfully.")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

    with auth_tab2:
        st.markdown('<div class="section-title">Create Account</div>', unsafe_allow_html=True)
        with st.form("register_form"):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email", key="reg_email")
            password = st.text_input("Password", type="password", key="reg_password")
            role = st.selectbox("Role", ["student", "teacher"])
            submit_register = st.form_submit_button("Create Account")

            if submit_register:
                try:
                    create_user(
                        full_name=full_name.strip(),
                        email=email.strip(),
                        password_hash=hash_password(password),
                        role=role
                    )
                    st.success("Account created. You can log in now.")
                except Exception as e:
                    st.error(f"Registration failed: {e}")

    st.stop()


# =========================
# Logged-In State
# =========================

current_user = get_user_by_id(st.session_state.user_id)

render_page_header()
st.write(f"Logged in as **{st.session_state.full_name}** ({st.session_state.role})")

header_col1, header_col2 = st.columns([8, 2])
with header_col2:
    if st.button("Logout"):
        logout_user()
        st.rerun()

notifications = load_notifications(current_user.id)
unread_count = sum(1 for n in notifications if n.is_read == 0)
st.caption(f"Unread notifications: {unread_count}")

settings = get_user_settings(current_user.id)
daily_hours = settings["daily_hours"]
break_minutes = settings["break_minutes"]

subjects = load_subjects_for_user(current_user.id)
chapters = load_chapters_for_user(current_user.id)
progress_records = load_progress_for_user(current_user.id)

role = current_user.role

sidebar_message = get_smart_sidebar_message(subjects, chapters, progress_records, role)

with st.sidebar:
    st.markdown("### 🌿 " + sidebar_message["title"])
    st.info(sidebar_message["text"])

base_tabs = ["Dashboard", "Plan", "Progress", "PDF Helper", "Notifications", "Settings"]

if role == "student":
    role_tabs = base_tabs + ["Subjects", "Chapters", "Analytics"]
elif role == "teacher":
    role_tabs = base_tabs + ["Teacher Panel", "Analytics"]
else:
    role_tabs = base_tabs + ["Admin Panel", "Analytics"]

tabs = st.tabs(role_tabs)
tab_map = {name: tab for name, tab in zip(role_tabs, tabs)}


# =========================
# Dashboard
# =========================

with tab_map["Dashboard"]:
    render_hero_section(st.session_state.full_name or "Student")

    st.write("")
    render_metric_pills(
        subjects_count=len(subjects),
        chapters_count=len(chapters),
        daily_hours=daily_hours,
        completion_rate=calculate_completion_rate(progress_records)
    )

    st.write("")

    if role == "student":
        today_plan = build_plan(subjects, chapters, daily_hours, progress_records)

        left_col, right_col = st.columns([1.5, 1])

        with left_col:
            render_pretty_tasks(today_plan)

            st.write("")
            st.markdown('<div class="section-title">Mini Progress View</div>', unsafe_allow_html=True)

            done_chapters = sum(1 for ch in chapters if ch.status == "done")
            in_progress_chapters = sum(1 for ch in chapters if ch.status == "in_progress")
            total_chapters = len(chapters)
            weak_chapters = sum(1 for ch in chapters if ch.weak == 1)

            progress_col1, progress_col2 = st.columns(2)

            with progress_col1:
                st.markdown(
                    f"""
                    <div class="soft-card">
                        <strong>Done Chapters</strong><br>
                        <div style="font-size:1.8rem; font-weight:800; margin-top:8px;">{done_chapters}</div>
                        <div class="small-muted">Out of {total_chapters} total chapters</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with progress_col2:
                st.markdown(
                    f"""
                    <div class="soft-card">
                        <strong>Weak Chapters</strong><br>
                        <div style="font-size:1.8rem; font-weight:800; margin-top:8px;">{weak_chapters}</div>
                        <div class="small-muted">Mark and revisit these first</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with right_col:
            st.markdown('<div class="section-title">Study Rhythm</div>', unsafe_allow_html=True)

            completion_rate = calculate_completion_rate(progress_records)
            chapter_completion_pct = round((done_chapters / total_chapters) * 100, 2) if total_chapters else 0
            in_progress_pct = round((in_progress_chapters / total_chapters) * 100, 2) if total_chapters else 0

            st.markdown('<div class="soft-card">', unsafe_allow_html=True)
            st.markdown("**Overall Completion**")
            st.progress(min(completion_rate / 100, 1.0), text=f"{completion_rate}%")

            st.markdown("**Chapters Completed**")
            st.progress(min(chapter_completion_pct / 100, 1.0), text=f"{chapter_completion_pct}%")

            st.markdown("**Currently In Progress**")
            st.progress(min(in_progress_pct / 100, 1.0), text=f"{in_progress_pct}%")
            st.markdown('</div>', unsafe_allow_html=True)

            st.write("")
            st.markdown('<div class="section-title">Quick Notes</div>', unsafe_allow_html=True)
            render_reminder_box()

            st.write("")
            st.markdown(
                """
                <div class="soft-card">
                    <strong>Best Order Today</strong><br><br>
                    1. Start with the hardest task<br>
                    2. Move to the most urgent task<br>
                    3. End with light revision
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")
            st.markdown(
                """
                <div class="soft-card">
                    <strong>Focus Advice</strong><br><br>
                    Use short, clean sessions. After each session:
                    <br>• summarize from memory
                    <br>• review mistakes
                    <br>• mark weak points
                </div>
                """,
                unsafe_allow_html=True
            )

    elif role == "teacher":
        my_classes = get_classes_for_teacher(current_user.id)

        st.markdown('<div class="section-title">Teacher Snapshot</div>', unsafe_allow_html=True)

        if my_classes:
            teacher_col1, teacher_col2 = st.columns([1.2, 1])

            with teacher_col1:
                st.dataframe(pd.DataFrame([c.to_dict() for c in my_classes]), use_container_width=True)

            with teacher_col2:
                st.markdown(
                    f"""
                    <div class="soft-card">
                        <strong>Total Classes</strong><br>
                        <div style="font-size:2rem; font-weight:800; margin-top:8px;">{len(my_classes)}</div>
                        <div class="small-muted">Classes currently assigned to you</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No classes assigned.")

    elif role == "admin":
        all_users = load_users()
        all_classes = load_classrooms()

        admin_col1, admin_col2 = st.columns(2)

        with admin_col1:
            st.markdown(
                f"""
                <div class="metric-pill metric-blue">
                    <h4>Total Users</h4>
                    <div class="metric-value">{len(all_users)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with admin_col2:
            st.markdown(
                f"""
                <div class="metric-pill metric-coral">
                    <h4>Total Classes</h4>
                    <div class="metric-value">{len(all_classes)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.write("")
        st.markdown(
            """
            <div class="soft-card">
                <strong>Admin Snapshot</strong><br>
                This dashboard gives a quick top-level view of platform usage and class structure.
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================
# Subjects
# =========================

if "Subjects" in tab_map:
    with tab_map["Subjects"]:
        st.subheader("Manage Subjects")

        classes_for_student = get_classes_for_student(current_user.id)

        with st.form("subject_form"):
            name = st.text_input("Subject Name")
            exam_date = st.date_input("Exam Date")
            level = st.selectbox("Level", ["weak", "medium", "good"])
            difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"])
            units = st.number_input("Units", min_value=1, max_value=100, value=10)
            subject_type = st.selectbox("Subject Type", ["problem_solving", "memory_heavy", "reading_heavy", "mixed"])
            preferred_hours = st.slider("Preferred Hours", 0.5, 4.0, 1.0, 0.5)

            class_options = {"None": None}
            for c in classes_for_student:
                class_options[c.name] = c.id

            selected_class = st.selectbox("Class (optional)", list(class_options.keys()))
            submit_subject = st.form_submit_button("Add Subject")

            if submit_subject:
                add_subject(
                    Subject(
                        id=None,
                        user_id=current_user.id,
                        class_id=class_options[selected_class],
                        name=name.strip(),
                        exam_date=str(exam_date),
                        level=level,
                        difficulty=difficulty,
                        units=int(units),
                        subject_type=subject_type,
                        preferred_hours=float(preferred_hours)
                    )
                )
                create_notification(current_user.id, "Subject Added", f"{name.strip()} was added successfully.")
                st.success("Subject added.")
                st.rerun()

        if subjects:
            st.dataframe(pd.DataFrame([s.to_dict() for s in subjects]), use_container_width=True)

            delete_label = st.selectbox("Delete Subject", [""] + [f"{s.id} - {s.name}" for s in subjects])
            if st.button("Delete Selected Subject"):
                if delete_label:
                    delete_subject(int(delete_label.split(" - ")[0]))
                    st.success("Subject deleted.")
                    st.rerun()


# =========================
# Chapters
# =========================

if "Chapters" in tab_map:
    with tab_map["Chapters"]:
        st.subheader("Manage Chapters")

        if not subjects:
            st.warning("Add subjects first.")
        else:
            subject_map = {f"{s.id} - {s.name}": s.id for s in subjects}

            with st.form("chapter_form"):
                subject_label = st.selectbox("Subject", list(subject_map.keys()))
                chapter_name = st.text_input("Chapter Name")
                chapter_difficulty = st.selectbox("Chapter Difficulty", ["easy", "medium", "hard"])
                chapter_status = st.selectbox("Status", ["not_started", "in_progress", "done"])
                chapter_weak = st.checkbox("Weak Chapter")
                add_btn = st.form_submit_button("Add Chapter")

                if add_btn:
                    add_chapter(
                        Chapter(
                            id=None,
                            subject_id=subject_map[subject_label],
                            name=chapter_name.strip(),
                            difficulty=chapter_difficulty,
                            status=chapter_status,
                            weak=1 if chapter_weak else 0
                        )
                    )
                    st.success("Chapter added.")
                    st.rerun()

            st.markdown("### Existing Chapters")
            chapter_rows = []
            for s in subjects:
                subject_chapters = load_chapters_for_subject(s.id)
                for ch in subject_chapters:
                    chapter_rows.append({
                        "id": ch.id,
                        "subject": s.name,
                        "chapter": ch.name,
                        "difficulty": ch.difficulty,
                        "status": chapter_status_badge(ch.status),
                        "weak": "Yes" if ch.weak else "No"
                    })

            if chapter_rows:
                st.dataframe(pd.DataFrame(chapter_rows), use_container_width=True)

            chapter_lookup = {}
            for s in subjects:
                for ch in load_chapters_for_subject(s.id):
                    label = f"{ch.id} - {s.name} - {ch.name}"
                    chapter_lookup[label] = ch

            if chapter_lookup:
                st.markdown("### Edit Chapter")
                selected_chapter_label = st.selectbox("Choose Chapter", list(chapter_lookup.keys()))
                selected_chapter = chapter_lookup[selected_chapter_label]

                new_name = st.text_input("Edit Name", value=selected_chapter.name)
                status_options = ["not_started", "in_progress", "done"]
                new_difficulty = st.selectbox(
                    "Edit Difficulty",
                    ["easy", "medium", "hard"],
                    index=["easy", "medium", "hard"].index(selected_chapter.difficulty)
                )
                new_status = st.selectbox(
                    "Edit Status",
                    status_options,
                    index=status_options.index(selected_chapter.status)
                )
                new_weak = st.checkbox("Weak", value=bool(selected_chapter.weak))

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Update Chapter"):
                        update_chapter(
                            chapter_id=selected_chapter.id,
                            name=new_name.strip(),
                            difficulty=new_difficulty,
                            status=new_status,
                            weak=1 if new_weak else 0
                        )
                        st.success("Chapter updated.")
                        st.rerun()

                with col2:
                    if st.button("Delete Chapter"):
                        delete_chapter(selected_chapter.id)
                        st.success("Chapter deleted.")
                        st.rerun()


# =========================
# Plan
# =========================

with tab_map["Plan"]:
    st.subheader("Study Plan")

    if role != "student":
        st.info("Planning is student-focused in this version.")
    else:
        today_plan = build_plan(subjects, chapters, daily_hours, progress_records)

        st.markdown('<div class="section-title">Today Plan</div>', unsafe_allow_html=True)
        if today_plan:
            render_pretty_tasks(today_plan)

            st.write("")
            st.markdown('<div class="section-title">Plan Table</div>', unsafe_allow_html=True)
            plan_df = pd.DataFrame(today_plan)
            st.dataframe(plan_df, use_container_width=True)

            st.download_button(
                "Download Plan CSV",
                data=df_to_csv_bytes(plan_df),
                file_name="today_plan.csv",
                mime="text/csv"
            )

            st.download_button(
                "Download Plan PDF",
                data=plan_to_pdf_bytes("Today Study Plan", today_plan),
                file_name="today_plan.pdf",
                mime="application/pdf"
            )

            st.markdown('<div class="section-title">Session Timeline</div>', unsafe_allow_html=True)
            session_df = pd.DataFrame(build_session_blocks(today_plan, break_minutes=break_minutes))
            st.dataframe(session_df, use_container_width=True)
        else:
            st.warning("No plan available.")

        st.markdown('<div class="section-title">Weekly Plan</div>', unsafe_allow_html=True)
        weekly_plan = generate_weekly_plan(subjects, chapters, daily_hours, progress_records)
        for day, tasks in weekly_plan.items():
            with st.expander(day):
                if tasks:
                    st.dataframe(pd.DataFrame(tasks), use_container_width=True)
                else:
                    st.write("No tasks.")


# =========================
# Progress
# =========================

with tab_map["Progress"]:
    st.subheader("Progress")

    if role != "student":
        st.info("Progress logging is student-focused in this version.")
    else:
        today_plan = build_plan(subjects, chapters, daily_hours, progress_records)

        if today_plan:
            task_map = {f"{t['subject']} | {t['chapter']}": t for t in today_plan}
            with st.form("progress_form"):
                date_value = st.date_input("Date", value=datetime.today().date())
                selected_task_label = st.selectbox("Task", list(task_map.keys()))
                selected_task = task_map[selected_task_label]
                completed_hours = st.slider("Completed Hours", 0.0, 6.0, 0.0, 0.5)
                status = st.selectbox("Status", ["completed", "partial", "skipped"])
                save_btn = st.form_submit_button("Save Progress")

                if save_btn:
                    add_progress(
                        ProgressRecord(
                            id=None,
                            user_id=current_user.id,
                            date=str(date_value),
                            subject=selected_task["subject"],
                            chapter=selected_task["chapter"],
                            planned_hours=selected_task["hours"],
                            completed_hours=float(completed_hours),
                            status=status
                        )
                    )
                    create_notification(
                        current_user.id,
                        "Progress Saved",
                        f"Progress logged for {selected_task['chapter']}."
                    )
                    st.success("Progress saved.")
                    st.rerun()

        if progress_records:
            progress_df = pd.DataFrame([p.to_dict() for p in progress_records])
            st.dataframe(progress_df, use_container_width=True)


# =========================
# PDF Helper
# =========================

with tab_map["PDF Helper"]:
    st.subheader("PDF Study Helper")
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])

    if uploaded_pdf:
        text = extract_text_from_pdf(uploaded_pdf)

        st.markdown("### Extracted Text Preview")
        st.text_area("Preview", text[:4000], height=250)

        st.markdown("### Summary")
        st.write(simple_summarize_text(text))

        st.markdown("### Keywords")
        keywords = extract_keywords(text)
        st.write(", ".join(keywords) if keywords else "No keywords extracted.")


# =========================
# Notifications
# =========================

with tab_map["Notifications"]:
    st.subheader("Notifications")

    if notifications:
        for n in notifications:
            read_state = "✅ Read" if n.is_read else "🔔 New"

            st.markdown(
                f"""
                <div class="soft-card" style="margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>{n.title}</strong>
                        <span class="small-muted">{read_state}</span>
                    </div>
                    <div style="margin-top:8px;">{n.message}</div>
                    <div class="small-muted" style="margin-top:8px;">{n.created_at}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if n.is_read == 0:
                if st.button(f"Mark as read #{n.id}"):
                    mark_notification_read(n.id)
                    st.rerun()
    else:
        st.info("No notifications.")


# =========================
# Settings
# =========================

with tab_map["Settings"]:
    st.subheader("Settings")

    with st.form("settings_form"):
        new_daily_hours = st.slider("Daily Study Hours", 1.0, 12.0, float(daily_hours), 0.5)
        new_break_minutes = st.slider("Break Minutes", 5, 30, int(break_minutes), 5)
        save_settings_btn = st.form_submit_button("Save Settings")

        if save_settings_btn:
            save_user_settings(current_user.id, new_daily_hours, new_break_minutes)
            st.success("Settings updated.")
            st.rerun()


# =========================
# Analytics
# =========================

with tab_map["Analytics"]:
    st.subheader("Analytics")

    if role == "student":
        completion_rate = calculate_completion_rate(progress_records)

        total_subjects = len(subjects)
        total_chapters = len(chapters)
        done_chapters = sum(1 for ch in chapters if ch.status == "done")
        in_progress_chapters = sum(1 for ch in chapters if ch.status == "in_progress")
        weak_chapters = sum(1 for ch in chapters if ch.weak == 1)

        st.markdown('<div class="section-title">Performance Snapshot</div>', unsafe_allow_html=True)

        k1, k2, k3, k4 = st.columns(4)

        with k1:
            st.markdown(
                f"""
                <div class="metric-pill metric-blue">
                    <h4>Completion Rate</h4>
                    <div class="metric-value">{completion_rate}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with k2:
            st.markdown(
                f"""
                <div class="metric-pill metric-yellow">
                    <h4>Subjects</h4>
                    <div class="metric-value">{total_subjects}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with k3:
            st.markdown(
                f"""
                <div class="metric-pill metric-pink">
                    <h4>Done Chapters</h4>
                    <div class="metric-value">{done_chapters}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with k4:
            st.markdown(
                f"""
                <div class="metric-pill metric-mint">
                    <h4>Weak Chapters</h4>
                    <div class="metric-value">{weak_chapters}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.write("")

        left_col, right_col = st.columns([1.4, 1])

        with left_col:
            st.markdown('<div class="section-title">Chapter Progress Overview</div>', unsafe_allow_html=True)

            chapter_completion_pct = round((done_chapters / total_chapters) * 100, 2) if total_chapters else 0
            in_progress_pct = round((in_progress_chapters / total_chapters) * 100, 2) if total_chapters else 0

            st.markdown("**Completed Chapters**")
            st.progress(min(chapter_completion_pct / 100, 1.0), text=f"{chapter_completion_pct}% completed")

            st.markdown("**In Progress Chapters**")
            st.progress(min(in_progress_pct / 100, 1.0), text=f"{in_progress_pct}% in progress")

            st.markdown("**Overall Study Completion**")
            st.progress(min(completion_rate / 100, 1.0), text=f"{completion_rate}% study completion")

        with right_col:
            st.markdown(
                f"""
                <div class="soft-card">
                    <strong>Study Insight</strong><br>
                    You currently have <strong>{weak_chapters}</strong> weak chapter(s).
                    Prioritize those before starting new low-priority content.
                </div>
                """,
                unsafe_allow_html=True
            )

            st.write("")

            st.markdown(
                """
                <div class="soft-card">
                    <strong>Recommendation</strong><br>
                    Focus first on: weak + in-progress chapters + subjects with near exam dates.
                </div>
                """,
                unsafe_allow_html=True
            )

        st.write("")

        summary = subject_completion_summary(progress_records)

        if summary:
            summary_df = pd.DataFrame([
                {"subject": subject, **data}
                for subject, data in summary.items()
            ])

            if "completion_rate" in summary_df.columns:
                summary_df = summary_df.sort_values(by="completion_rate", ascending=False)

            st.markdown('<div class="section-title">Subject Ranking</div>', unsafe_allow_html=True)

            col1, col2 = st.columns([1.3, 1])

            with col1:
                st.dataframe(summary_df, use_container_width=True)

            with col2:
                if not summary_df.empty:
                    top_subject = summary_df.iloc[0]["subject"]
                    top_rate = summary_df.iloc[0]["completion_rate"]

                    low_subject = summary_df.iloc[-1]["subject"]
                    low_rate = summary_df.iloc[-1]["completion_rate"]

                    st.markdown(
                        f"""
                        <div class="soft-card">
                            <strong>Top Performing Subject</strong><br>
                            {top_subject} — {top_rate}%<br><br>
                            <strong>Needs More Attention</strong><br>
                            {low_subject} — {low_rate}%
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.markdown('<div class="section-title">Planned vs Completed Hours</div>', unsafe_allow_html=True)
            chart_df = summary_df.set_index("subject")[["planned", "completed"]]
            st.bar_chart(chart_df)

        else:
            st.info("No progress data available yet.")

        if subjects:
            readiness_rows = []

            for s in subjects:
                subject_chapters = load_chapters_for_subject(s.id)
                readiness_rows.append({
                    "subject": s.name,
                    "readiness_score": readiness_score(s, subject_chapters, progress_records)
                })

            readiness_df = pd.DataFrame(readiness_rows).sort_values(by="readiness_score", ascending=False)

            st.markdown('<div class="section-title">Exam Readiness</div>', unsafe_allow_html=True)

            col1, col2 = st.columns([1.3, 1])

            with col1:
                st.dataframe(readiness_df, use_container_width=True)

            with col2:
                if not readiness_df.empty:
                    best_subject = readiness_df.iloc[0]["subject"]
                    best_score = readiness_df.iloc[0]["readiness_score"]

                    st.markdown(
                        f"""
                        <div class="soft-card">
                            <strong>Highest Readiness</strong><br>
                            {best_subject} — {best_score}%<br><br>
                            This subject currently has the strongest coverage and completion pattern.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

            st.bar_chart(readiness_df.set_index("subject"))

        if chapters:
            st.markdown('<div class="section-title">Chapter Status Distribution</div>', unsafe_allow_html=True)

            distribution = chapter_status_distribution(chapters)
            dist_df = pd.DataFrame({
                "status": list(distribution.keys()),
                "count": list(distribution.values())
            }).set_index("status")

            col1, col2 = st.columns([1.3, 1])

            with col1:
                st.bar_chart(dist_df)

            with col2:
                weak_rows = []
                subject_name_lookup = {s.id: s.name for s in subjects}

                for ch in chapters:
                    if ch.weak == 1:
                        weak_rows.append({
                            "subject": subject_name_lookup.get(ch.subject_id, "Unknown"),
                            "chapter": ch.name,
                            "status": ch.status
                        })

                st.markdown('<div class="section-title">Weak Areas</div>', unsafe_allow_html=True)

                if weak_rows:
                    weak_df = pd.DataFrame(weak_rows)
                    st.dataframe(weak_df, use_container_width=True)
                else:
                    st.markdown(
                        """
                        <div class="soft-card">
                            No weak chapters marked yet.
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    elif role == "teacher":
        st.markdown('<div class="section-title">Teacher Overview</div>', unsafe_allow_html=True)

        my_classes = get_classes_for_teacher(current_user.id)

        if my_classes:
            st.markdown(
                f"""
                <div class="soft-card" style="margin-bottom:16px;">
                    <strong>Total Classes</strong><br>
                    {len(my_classes)} class(es) assigned to you.
                </div>
                """,
                unsafe_allow_html=True
            )

            for c in my_classes:
                with st.expander(f"Class: {c.name}"):
                    students = get_students_in_class(c.id)

                    if students:
                        students_df = pd.DataFrame([
                            {
                                "id": s.id,
                                "name": s.full_name,
                                "email": s.email
                            }
                            for s in students
                        ])
                        st.dataframe(students_df, use_container_width=True)

                        st.markdown(
                            """
                            <div class="soft-card">
                                <strong>Teacher Insight</strong><br>
                                Use class membership as a quick view for engagement tracking and academic follow-up.
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.info("No students in this class.")
        else:
            st.info("No classes assigned.")

    elif role == "admin":
        all_users = load_users()
        all_classes = load_classrooms()

        students_count = len([u for u in all_users if u.role == "student"])
        teachers_count = len([u for u in all_users if u.role == "teacher"])
        admins_count = len([u for u in all_users if u.role == "admin"])

        st.markdown('<div class="section-title">System Snapshot</div>', unsafe_allow_html=True)

        a1, a2, a3, a4 = st.columns(4)

        with a1:
            st.markdown(
                f"""
                <div class="metric-pill metric-blue">
                    <h4>Total Users</h4>
                    <div class="metric-value">{len(all_users)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with a2:
            st.markdown(
                f"""
                <div class="metric-pill metric-coral">
                    <h4>Students</h4>
                    <div class="metric-value">{students_count}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with a3:
            st.markdown(
                f"""
                <div class="metric-pill metric-yellow">
                    <h4>Teachers</h4>
                    <div class="metric-value">{teachers_count}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with a4:
            st.markdown(
                f"""
                <div class="metric-pill metric-mint">
                    <h4>Classes</h4>
                    <div class="metric-value">{len(all_classes)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.write("")

        roles_df = pd.DataFrame({
            "role": ["student", "teacher", "admin"],
            "count": [students_count, teachers_count, admins_count]
        }).set_index("role")

        st.markdown('<div class="section-title">User Role Distribution</div>', unsafe_allow_html=True)
        st.bar_chart(roles_df)

        st.markdown(
            """
            <div class="soft-card" style="margin-top:16px;">
                <strong>Admin Insight</strong><br>
                A balanced growth in classes, teachers, and students reflects healthier platform structure.
            </div>
            """,
            unsafe_allow_html=True
        )


# =========================
# Teacher Panel
# =========================

if "Teacher Panel" in tab_map:
    with tab_map["Teacher Panel"]:
        st.subheader("Teacher Panel")

        st.markdown("### Create Class")
        with st.form("teacher_create_class"):
            class_name = st.text_input("Class Name")
            create_class_btn = st.form_submit_button("Create Class")
            if create_class_btn:
                create_classroom(class_name.strip(), current_user.id)
                st.success("Class created.")
                st.rerun()

        teacher_classes = get_classes_for_teacher(current_user.id)

        st.markdown("### My Classes")
        if teacher_classes:
            st.dataframe(pd.DataFrame([c.to_dict() for c in teacher_classes]), use_container_width=True)

            students = load_users("student")
            class_lookup = {f"{c.id} - {c.name}": c.id for c in teacher_classes}
            student_lookup = {f"{s.id} - {s.full_name}": s.id for s in students}

            if students:
                with st.form("assign_student_form"):
                    selected_class = st.selectbox("Class", list(class_lookup.keys()))
                    selected_student = st.selectbox("Student", list(student_lookup.keys()))
                    assign_btn = st.form_submit_button("Assign Student")

                    if assign_btn:
                        assign_student_to_class(class_lookup[selected_class], student_lookup[selected_student])
                        create_notification(
                            student_lookup[selected_student],
                            "Class Assignment",
                            f"You were assigned to class {selected_class}."
                        )
                        st.success("Student assigned.")
                        st.rerun()

            st.markdown("### Class Students")
            class_for_view = st.selectbox("View students of class", list(class_lookup.keys()), key="teacher_view_class")
            selected_class_id = class_lookup[class_for_view]
            class_students = get_students_in_class(selected_class_id)
            if class_students:
                st.dataframe(pd.DataFrame([{
                    "id": s.id,
                    "name": s.full_name,
                    "email": s.email
                } for s in class_students]), use_container_width=True)
            else:
                st.info("No students yet.")
        else:
            st.info("No classes found.")


# =========================
# Admin Panel
# =========================

if "Admin Panel" in tab_map:
    with tab_map["Admin Panel"]:
        st.subheader("Admin Panel")

        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Users", "Classes", "Reset"])

        with admin_tab1:
            st.markdown("### Create User")
            with st.form("admin_create_user"):
                full_name = st.text_input("Full Name", key="admin_user_name")
                email = st.text_input("Email", key="admin_user_email")
                password = st.text_input("Password", type="password", key="admin_user_password")
                role_select = st.selectbox("Role", ["student", "teacher", "admin"], key="admin_role")
                create_user_btn = st.form_submit_button("Create User")

                if create_user_btn:
                    try:
                        create_user(full_name.strip(), email.strip(), hash_password(password), role_select)
                        st.success("User created.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create user: {e}")

            st.markdown("### All Users")
            all_users = load_users()
            if all_users:
                st.dataframe(pd.DataFrame([{
                    "id": u.id,
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": u.role
                } for u in all_users]), use_container_width=True)

        with admin_tab2:
            teachers = load_users("teacher")
            teacher_map = {"None": None}
            for t in teachers:
                teacher_map[f"{t.id} - {t.full_name}"] = t.id

            with st.form("admin_create_class"):
                class_name = st.text_input("Class Name", key="admin_class_name")
                teacher_label = st.selectbox("Assign Teacher", list(teacher_map.keys()))
                create_class_btn = st.form_submit_button("Create Class")

                if create_class_btn:
                    create_classroom(class_name.strip(), teacher_map[teacher_label])
                    st.success("Class created.")
                    st.rerun()

            all_classes = load_classrooms()
            if all_classes:
                class_rows = []
                for c in all_classes:
                    teacher_name = "Unassigned"
                    if c.teacher_id:
                        teacher = get_user_by_id(c.teacher_id)
                        teacher_name = teacher.full_name if teacher else "Unknown"
                    class_rows.append({
                        "id": c.id,
                        "name": c.name,
                        "teacher": teacher_name
                    })
                st.dataframe(pd.DataFrame(class_rows), use_container_width=True)

        with admin_tab3:
            st.warning("This removes all non-admin data.")
            if st.button("Reset All Data"):
                reset_database_data()
                st.success("Database reset completed.")
                st.rerun()