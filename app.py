from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vards TEXT,
            uzvards TEXT,
            klase TEXT,
            email TEXT UNIQUE,
            parole TEXT,
            role TEXT DEFAULT 'user'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS olimpiades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nosaukums TEXT,
            apraksts TEXT,
            prieksmets TEXT,
            datums TEXT,
            pieteiksanas_lidz TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS pieteikumi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            olimpiade_id INTEGER,
            UNIQUE(user_id, olimpiade_id)
        )
    """)

    conn.commit()

    # Create default admin if not exists
    c.execute("SELECT * FROM users WHERE email='admin@admin.lv'")
    if not c.fetchone():
        c.execute("""
            INSERT INTO users (vards, uzvards, klase, email, parole, role)
            VALUES ('Admin', 'Admin', '-', 'admin@admin.lv', 'admin123', 'admin')
        """)

    conn.commit()
    conn.close()


init_db()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        parole = request.form["parole"]

        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND parole=?", (email, parole))
        user = c.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["vards"] = user[1]
            session["role"] = user[6]
            return redirect("/home")

    return render_template("login.html")


@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT * FROM olimpiades")
    olimpiades = c.fetchall()

    c.execute("""
        SELECT olimpiades.*
        FROM olimpiades
        JOIN pieteikumi ON olimpiades.id = pieteikumi.olimpiade_id
        WHERE pieteikumi.user_id=?
    """, (session["user_id"],))
    mani = c.fetchall()

    conn.close()

    return render_template("home.html",
                           vards=session["vards"],
                           olimpiades=olimpiades,
                           mani=mani,
                           role=session["role"])

@app.route("/pieteikties/<int:id>")
def pieteikties(id):
    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO pieteikumi (user_id, olimpiade_id) VALUES (?, ?)",
                  (session["user_id"], id))
        conn.commit()
    except:
        pass  # already applied

    conn.close()
    return redirect("/home")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "role" not in session or session["role"] != "admin":
        return redirect("/home")

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    if request.method == "POST":
        nosaukums = request.form["nosaukums"]
        apraksts = request.form["apraksts"]
        prieksmets = request.form["prieksmets"]
        datums = request.form["datums"]
        pieteiksanas = request.form["pieteiksanas"]

        c.execute("""
            INSERT INTO olimpiades (nosaukums, apraksts, prieksmets, datums, pieteiksanas_lidz)
            VALUES (?, ?, ?, ?, ?)
        """, (nosaukums, apraksts, prieksmets, datums, pieteiksanas))

        conn.commit()

    c.execute("SELECT * FROM olimpiades")
    olimpiades = c.fetchall()

    conn.close()

    return render_template("admin.html", olimpiades=olimpiades)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
