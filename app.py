from __future__ import annotations

import io
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    send_file,
)
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from openpyxl.styles import Font

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY"
DB_PATH = "olymp.db"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_iso() -> str:
    return datetime.now().date().isoformat()


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        class_name TEXT,
        role TEXT NOT NULL DEFAULT 'student',
        teacher_id INTEGER,
        subject_name TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS olympiads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        event_date TEXT NOT NULL,
        level_name TEXT NOT NULL,
        deadline TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        olympiad_id INTEGER NOT NULL,
        student_phone TEXT NOT NULL,
        guardian_name TEXT NOT NULL,
        guardian_phone TEXT NOT NULL,
        motivation TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, olympiad_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(olympiad_id) REFERENCES olympiads(id)
    )
    """)

    conn.commit()

    # Admin konts
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@skola.lv",))
    if cur.fetchone() is None:
        cur.execute("""
            INSERT INTO users (
                full_name, email, password_hash, class_name, role,
                teacher_id, subject_name, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Administrators",
            "admin@skola.lv",
            generate_password_hash("Admin123!"),
            "",
            "admin",
            None,
            None,
            now_utc_iso()
        ))
        conn.commit()

    # Demo skolotāji
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'teacher'")
    if cur.fetchone()["c"] == 0:
        demo_teachers = [
            ("Māra Bērziņa", "mara.berzina@skola.lv", "Matemātika", "Skolotaja123!"),
            ("Ilze Kalniņa", "ilze.kalnina@skola.lv", "Fizika", "Skolotaja123!"),
        ]
        for full_name, email, subject_name, password in demo_teachers:
            cur.execute("""
                INSERT INTO users (
                    full_name, email, password_hash, class_name, role,
                    teacher_id, subject_name, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                full_name,
                email,
                generate_password_hash(password),
                "",
                "teacher",
                None,
                subject_name,
                now_utc_iso()
            ))
        conn.commit()

    # Demo olimpiādes
    cur.execute("SELECT COUNT(*) AS c FROM olympiads")
    if cur.fetchone()["c"] == 0:
        seed = [
            (
                "Matemātikas olimpiāde 2026",
                "Matemātika",
                "Skolēnu matemātikas olimpiāde visiem klašu līmeņiem. Uzdevumi pārbauda loģisko domāšanu un problēmu risināšanas prasmes.",
                "2026-12-15",
                "Skolas",
                "2026-12-01"
            ),
            (
                "Fizikas olimpiāde 2026",
                "Fizika",
                "Ikgadējā fizikas olimpiāde vidusskolēniem. Teorētiskie un eksperimentālie uzdevumi.",
                "2026-12-22",
                "Skolas",
                "2026-12-08"
            ),
        ]
        for title, subject, description, event_date, level_name, deadline in seed:
            cur.execute("""
                INSERT INTO olympiads (
                    title, subject, description, event_date,
                    level_name, deadline, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                title,
                subject,
                description,
                event_date,
                level_name,
                deadline,
                now_utc_iso()
            ))
        conn.commit()

    conn.close()


@app.before_request
def ensure_db() -> None:
    init_db()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth"))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth"))
        if session.get("role") != "admin":
            flash("Nav piekļuves šai sadaļai.", "error")
            return redirect(url_for("home"))
        return fn(*args, **kwargs)
    return wrapper


@app.get("/")
def index():
    return redirect(url_for("auth"))


@app.get("/auth")
def auth():
    if "user_id" in session:
        return redirect(url_for("home"))

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, full_name, subject_name
        FROM users
        WHERE role = 'teacher'
        ORDER BY full_name
    """)
    teachers = cur.fetchall()
    conn.close()

    return render_template("auth.html", teachers=teachers)


@app.post("/register")
def register():
    role = request.form.get("role", "student").strip()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()
    class_name = request.form.get("class_name", "").strip()
    teacher_id = request.form.get("teacher_id", "").strip()

    if role == "teacher":
        flash("Skolotāju kontus veido administrators.", "error")
        return redirect(url_for("auth"))

    if not full_name or not email or not password or not class_name or not teacher_id:
        flash("Aizpildi visus skolēna reģistrācijas laukus.", "error")
        return redirect(url_for("auth"))

    if len(password) < 6:
        flash("Parolei jābūt vismaz 6 simboliem.", "error")
        return redirect(url_for("auth"))

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'teacher'",
        (teacher_id,)
    )
    teacher = cur.fetchone()
    if teacher is None:
        conn.close()
        flash("Izvēlētais skolotājs nav atrasts.", "error")
        return redirect(url_for("auth"))

    try:
        cur.execute("""
            INSERT INTO users (
                full_name, email, password_hash, class_name,
                role, teacher_id, subject_name, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            email,
            generate_password_hash(password),
            class_name,
            "student",
            int(teacher_id),
            None,
            now_utc_iso()
        ))
        conn.commit()
        flash("Konts izveidots. Tagad vari ielogoties.", "ok")
    except sqlite3.IntegrityError:
        flash("Šāds e-pasts jau ir reģistrēts.", "error")
    finally:
        conn.close()

    return redirect(url_for("auth"))


@app.post("/login")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "").strip()

    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Nepareizs e-pasts vai parole.", "error")
        return redirect(url_for("auth"))

    session["user_id"] = user["id"]
    session["full_name"] = user["full_name"]
    session["role"] = user["role"]

    return redirect(url_for("home"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth"))


@app.get("/home")
@login_required
def home():
    role = session.get("role")
    conn = db()
    cur = conn.cursor()

    if role == "student":
        cur.execute("""
            SELECT COUNT(*) AS c
            FROM olympiads
            WHERE deadline >= ?
        """, (today_iso(),))
        olymp_count = cur.fetchone()["c"]

        cur.execute("""
            SELECT COUNT(*) AS c
            FROM applications
            WHERE user_id = ?
        """, (session["user_id"],))
        my_apps_count = cur.fetchone()["c"]

        cur.execute("""
            SELECT o.*,
                   EXISTS(
                       SELECT 1
                       FROM applications a
                       WHERE a.user_id = ? AND a.olympiad_id = o.id
                   ) AS already_applied
            FROM olympiads o
            WHERE o.deadline >= ?
            ORDER BY o.deadline ASC, o.event_date ASC
        """, (session["user_id"], today_iso()))
        olympiads = cur.fetchall()

        cur.execute("""
            SELECT
                a.id,
                a.created_at,
                o.title,
                o.subject,
                o.event_date,
                o.deadline,
                o.level_name
            FROM applications a
            JOIN olympiads o ON o.id = a.olympiad_id
            WHERE a.user_id = ?
            ORDER BY a.created_at DESC
        """, (session["user_id"],))
        my_apps = cur.fetchall()

        cur.execute("""
            SELECT t.full_name, t.subject_name
            FROM users s
            LEFT JOIN users t ON t.id = s.teacher_id
            WHERE s.id = ?
        """, (session["user_id"],))
        teacher_info = cur.fetchone()

        conn.close()
        return render_template(
            "home.html",
            role="student",
            olymp_count=olymp_count,
            my_apps_count=my_apps_count,
            teacher_info=teacher_info,
            olympiads=olympiads,
            my_apps=my_apps,
        )

    if role == "teacher":
        cur.execute("""
            SELECT id, full_name, class_name, email
            FROM users
            WHERE role = 'student' AND teacher_id = ?
            ORDER BY class_name, full_name
        """, (session["user_id"],))
        students = cur.fetchall()

        cur.execute("""
            SELECT
                a.id,
                a.created_at,
                s.full_name AS student_name,
                s.class_name,
                o.title,
                o.subject,
                o.event_date,
                o.deadline
            FROM applications a
            JOIN users s ON s.id = a.user_id
            JOIN olympiads o ON o.id = a.olympiad_id
            WHERE s.teacher_id = ?
            ORDER BY a.created_at DESC
        """, (session["user_id"],))
        student_apps = cur.fetchall()

        conn.close()
        return render_template(
            "home.html",
            role="teacher",
            students=students,
            student_apps=student_apps,
        )

    # admin
    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'teacher'")
    teacher_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'student'")
    student_count = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM applications")
    application_count = cur.fetchone()["c"]

    conn.close()
    return render_template(
        "home.html",
        role="admin",
        teacher_count=teacher_count,
        student_count=student_count,
        application_count=application_count,
    )


@app.post("/apply")
@login_required
def apply():
    if session.get("role") != "student":
        flash("Pieteikties var tikai skolēns.", "error")
        return redirect(url_for("home"))

    olympiad_id = request.form.get("olympiad_id", "").strip()
    student_phone = request.form.get("student_phone", "").strip()
    guardian_name = request.form.get("guardian_name", "").strip()
    guardian_phone = request.form.get("guardian_phone", "").strip()
    motivation = request.form.get("motivation", "").strip()

    if not olympiad_id or not student_phone or not guardian_name or not guardian_phone:
        flash("Aizpildi obligātos laukus.", "error")
        return redirect(url_for("home"))

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM olympiads WHERE id = ?", (olympiad_id,))
    olympiad = cur.fetchone()

    if olympiad is None:
        conn.close()
        flash("Olimpiāde nav atrasta.", "error")
        return redirect(url_for("home"))

    if olympiad["deadline"] < today_iso():
        conn.close()
        flash("Pieteikšanās termiņš ir beidzies.", "error")
        return redirect(url_for("home"))

    try:
        cur.execute("""
            INSERT INTO applications (
                user_id, olympiad_id, student_phone,
                guardian_name, guardian_phone, motivation, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            int(olympiad_id),
            student_phone,
            guardian_name,
            guardian_phone,
            motivation if motivation else None,
            now_utc_iso()
        ))
        conn.commit()
        flash("Pieteikums nosūtīts.", "ok")
    except sqlite3.IntegrityError:
        flash("Tu jau esi pieteicies šai olimpiādei.", "error")
    finally:
        conn.close()

    return redirect(url_for("home"))


@app.post("/applications/<int:application_id>/cancel")
@login_required
def cancel_application(application_id: int):
    if session.get("role") != "student":
        flash("Šī darbība nav atļauta.", "error")
        return redirect(url_for("home"))

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM applications
        WHERE id = ? AND user_id = ?
    """, (application_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Pieteikums atcelts.", "ok")
    return redirect(url_for("home"))


@app.get("/admin")
@admin_required
def admin():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, full_name, email, subject_name
        FROM users
        WHERE role = 'teacher'
        ORDER BY full_name
    """)
    teachers = cur.fetchall()

    cur.execute("""
        SELECT *
        FROM olympiads
        ORDER BY created_at DESC
    """)
    olympiads = cur.fetchall()

    cur.execute("""
        SELECT DISTINCT subject
        FROM olympiads
        ORDER BY subject
    """)
    subjects = cur.fetchall()

    conn.close()
    return render_template(
        "admin.html",
        teachers=teachers,
        olympiads=olympiads,
        subjects=subjects,
    )


@app.post("/admin/teachers/create")
@admin_required
def create_teacher():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    subject_name = request.form.get("subject_name", "").strip()
    password = request.form.get("password", "").strip()

    if not full_name or not email or not subject_name or not password:
        flash("Aizpildi visus skolotāja laukus.", "error")
        return redirect(url_for("admin"))

    if len(password) < 6:
        flash("Parolei jābūt vismaz 6 simboliem.", "error")
        return redirect(url_for("admin"))

    conn = db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (
                full_name, email, password_hash, class_name,
                role, teacher_id, subject_name, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            full_name,
            email,
            generate_password_hash(password),
            "",
            "teacher",
            None,
            subject_name,
            now_utc_iso()
        ))
        conn.commit()
        flash("Skolotājs pievienots.", "ok")
    except sqlite3.IntegrityError:
        flash("Šāds e-pasts jau eksistē.", "error")
    finally:
        conn.close()

    return redirect(url_for("admin"))


@app.post("/admin/olympiads/create")
@admin_required
def create_olympiad():
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    description = request.form.get("description", "").strip()
    event_date = request.form.get("event_date", "").strip()
    level_name = request.form.get("level_name", "").strip()
    deadline = request.form.get("deadline", "").strip()

    if not all([title, subject, description, event_date, level_name, deadline]):
        flash("Aizpildi visus olimpiādes laukus.", "error")
        return redirect(url_for("admin"))

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO olympiads (
            title, subject, description, event_date,
            level_name, deadline, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        subject,
        description,
        event_date,
        level_name,
        deadline,
        now_utc_iso()
    ))

    conn.commit()
    conn.close()

    flash("Olimpiāde pievienota.", "ok")
    return redirect(url_for("admin"))


@app.get("/admin/export-applications")
@admin_required
def export_applications():
    subject_filter = request.args.get("subject", "").strip()
    teacher_id_filter = request.args.get("teacher_id", "").strip()

    conn = db()
    cur = conn.cursor()

    query = """
        SELECT
            o.subject AS olympiad_subject,
            t.full_name AS teacher_name,
            t.subject_name AS teacher_subject,
            s.full_name AS student_name,
            s.class_name AS class_name,
            s.email AS student_email,
            o.title AS olympiad_title,
            o.event_date AS event_date,
            o.deadline AS deadline,
            a.created_at AS application_created_at
        FROM applications a
        JOIN users s ON s.id = a.user_id
        LEFT JOIN users t ON t.id = s.teacher_id
        JOIN olympiads o ON o.id = a.olympiad_id
        WHERE 1=1
    """
    params = []

    if subject_filter:
        query += " AND o.subject = ?"
        params.append(subject_filter)

    if teacher_id_filter:
        query += " AND t.id = ?"
        params.append(teacher_id_filter)

    query += " ORDER BY o.subject, t.full_name, s.class_name, s.full_name"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Pieteikumi"

    headers = [
        "Olimpiādes priekšmets",
        "Skolotājs",
        "Skolotāja priekšmets",
        "Skolēns",
        "Klase",
        "Skolēna e-pasts",
        "Olimpiāde",
        "Olimpiādes datums",
        "Pieteikšanās termiņš",
        "Pieteikuma izveides laiks",
    ]
    ws.append(headers)

    for cell in ws[1]:
        cell.font = Font(bold=True)

    for row in rows:
        ws.append([
            row["olympiad_subject"],
            row["teacher_name"],
            row["teacher_subject"],
            row["student_name"],
            row["class_name"],
            row["student_email"],
            row["olympiad_title"],
            row["event_date"],
            row["deadline"],
            row["application_created_at"],
        ])

    widths = {
        "A": 22, "B": 24, "C": 20, "D": 24, "E": 12,
        "F": 28, "G": 28, "H": 18, "I": 20, "J": 28,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="olimpiadu_pieteikumi.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(debug=True)

