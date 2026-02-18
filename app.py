from __future__ import annotations

import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "CHANGE_ME_TO_SOMETHING_RANDOM"
DB_PATH = "olymp.db"


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
        created_at TEXT NOT NULL
    );
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
    );
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
    );
    """)

    conn.commit()


    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@skola.lv",))
    if cur.fetchone() is None:
        cur.execute("""
            INSERT INTO users(full_name, email, password_hash, class_name, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "Administrators",
            "admin@skola.lv",
            generate_password_hash("Admin123!"),
            "",
            "admin",
            datetime.utcnow().isoformat()
        ))
        conn.commit()


    cur.execute("SELECT COUNT(*) as c FROM olympiads;")
    if cur.fetchone()["c"] == 0:
        seed = [
            (
                "Matemātikas olimpiāde 2026",
                "Matemātika",
                "Skolēnu matemātikas olimpiāde visiem klašu līmeņiem. Uzdevumi pārbauda loģisko domāšanu un problēmu risināšanas prasmes.",
                "2026-02-15",
                "Skolas",
                "2026-02-01"
            ),
            (
                "Fizikas olimpiāde 2026",
                "Fizika",
                "Ikgadējā fizikas olimpiāde vidusskolēniem. Teorētiskie un eksperimentālie uzdevumi.",
                "2026-02-22",
                "Skolas",
                "2026-02-08"
            ),
        ]
        for t, s, d, ed, lvl, dl in seed:
            cur.execute("""
                INSERT INTO olympiads(title, subject, description, event_date, level_name, deadline, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (t, s, d, ed, lvl, dl, datetime.utcnow().isoformat()))
        conn.commit()

    conn.close()


@app.before_request
def _ensure_db():
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
            flash("Nav piekļuves: nepieciešamas administratora tiesības.", "error")
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
    return render_template("auth.html")


@app.post("/register")
def register():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    class_name = request.form.get("class_name", "").strip()

    if not full_name or not email or not password:
        flash("Aizpildi vārdu, e-pastu un paroli.", "error")
        return redirect(url_for("auth"))

    if len(password) < 6:
        flash("Parolei jābūt vismaz 6 simboli.", "error")
        return redirect(url_for("auth"))

    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users(full_name, email, password_hash, class_name, role, created_at)
            VALUES (?, ?, ?, ?, 'student', ?)
        """, (full_name, email, generate_password_hash(password), class_name, datetime.utcnow().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Šāds e-pasts jau ir reģistrēts.", "error")
        return redirect(url_for("auth"))
    finally:
        conn.close()

    flash("Konts izveidots! Tagad vari ielogoties.", "ok")
    return redirect(url_for("auth"))


@app.post("/login")
def login():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

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
    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as c FROM olympiads;")
    olymp_count = cur.fetchone()["c"]

    cur.execute("""
        SELECT a.id
        FROM applications a
        WHERE a.user_id = ?
    """, (session["user_id"],))
    my_apps_count = len(cur.fetchall())


    cur.execute("""
        SELECT deadline
        FROM olympiads
        ORDER BY deadline ASC
        LIMIT 1
    """)
    row = cur.fetchone()
    soonest_deadline = row["deadline"] if row else None


    cur.execute("""
        SELECT o.*,
        EXISTS(
            SELECT 1 FROM applications a
            WHERE a.user_id = ? AND a.olympiad_id = o.id
        ) as already_applied
        FROM olympiads o
        ORDER BY o.deadline ASC, o.event_date ASC
    """, (session["user_id"],))
    olympiads = cur.fetchall()


    cur.execute("""
        SELECT a.*, o.title, o.subject, o.event_date, o.deadline, o.level_name
        FROM applications a
        JOIN olympiads o ON o.id = a.olympiad_id
        WHERE a.user_id = ?
        ORDER BY a.created_at DESC
    """, (session["user_id"],))
    my_apps = cur.fetchall()

    conn.close()

    return render_template(
        "home.html",
        olymp_count=olymp_count,
        my_apps_count=my_apps_count,
        soonest_deadline=soonest_deadline,
        olympiads=olympiads,
        my_apps=my_apps,
        is_admin=(session.get("role") == "admin")
    )


@app.post("/apply")
@login_required
def apply():

    olympiad_id = request.form.get("olympiad_id", "").strip()
    student_phone = request.form.get("student_phone", "").strip()
    guardian_name = request.form.get("guardian_name", "").strip()
    guardian_phone = request.form.get("guardian_phone", "").strip()
    motivation = request.form.get("motivation", "").strip()

    if not olympiad_id or not student_phone or not guardian_name or not guardian_phone:
        flash("Aizpildi obligātos laukus (tālrunis, vecāks/aizbildnis, vecāka tālrunis).", "error")
        return redirect(url_for("home"))

    conn = db()
    cur = conn.cursor()


    cur.execute("SELECT id FROM olympiads WHERE id = ?", (olympiad_id,))
    if cur.fetchone() is None:
        conn.close()
        flash("Olimpiāde nav atrasta.", "error")
        return redirect(url_for("home"))


    try:
        cur.execute("""
            INSERT INTO applications(user_id, olympiad_id, student_phone, guardian_name, guardian_phone, motivation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            int(olympiad_id),
            student_phone,
            guardian_name,
            guardian_phone,
            motivation if motivation else None,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        flash("Tu jau esi pieteicies šai olimpiādei.", "error")
    finally:
        conn.close()

    flash("Pieteikums nosūtīts ✅", "ok")
    return redirect(url_for("home"))


@app.get("/admin")
@admin_required
def admin():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM olympiads ORDER BY created_at DESC")
    olympiads = cur.fetchall()
    conn.close()
    return render_template("admin.html", olympiads=olympiads)


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
        flash("Aizpildi visus laukus.", "error")
        return redirect(url_for("admin"))

    conn = db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO olympiads(title, subject, description, event_date, level_name, deadline, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (title, subject, description, event_date, level_name, deadline, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

    flash("Olimpiāde pievienota.", "ok")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)
