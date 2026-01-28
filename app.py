from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecret"

DB = "olimpiades.db"

def get_db():
    return sqlite3.connect(DB)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        parole = request.form["parole"]

        db = get_db()
        cur = db.cursor()
        cur.execute(
            "SELECT id, vards FROM lietotajs WHERE epasts=? AND parole=?",
            (email, parole)
        )
        user = cur.fetchone()

        if user:
            session["user_id"] = user[0]
            session["vards"] = user[1]
            return redirect("/home")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        vards = request.form["vards"]
        uzvards = request.form["uzvards"]
        email = request.form["email"]
        parole = request.form["parole"]
        klase = request.form["klase"]

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO lietotajs (vards, uzvards, epasts, parole, loma)
            VALUES (?, ?, ?, ?, 'skolens')
        """, (vards, uzvards, email, parole))
        db.commit()

        return redirect("/")

    return render_template("register.html")

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")
    return render_template("home.html", vards=session["vards"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
