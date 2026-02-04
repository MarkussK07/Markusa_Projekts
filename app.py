from flask import Flask, render_template, request, redirect, session
import sqlite3 
import hashlib

app = Flask(__name__)
app.secret_key = "secret123"

USERNAME = "arturix@arturix.lv"
HASH ="9e03f8af886ffe78a5fcd5e4827af673" #Parole: Tests123!

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        username= request.form.get("username") 
        password = request.form.get("pwd")
        print(username)
        print(password)

        hashed = hashlib.md5(password.encode("utf-8")).hexdigest()
        print (hashed)

        if username == USERNAME and hashed == HASH:
            return render_template("home.html", username-username)
        else:
            error = "Nepareizs lietotājvārds vai parole"

        return render_template("login.html", error-error)


DB = "PD_DB.db"

def get_db():
    return sqlite3.connect(DB)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        mode = request.form.get("mode")

        email = request.form.get("email")
        parole = request.form.get("parole")

        db = get_db()
        cur = db.cursor()

        if mode == "login":
            cur.execute(
                "SELECT id, vards FROM lietotajs WHERE epasts=? AND parole=?",
                (email, parole)
            )
            user = cur.fetchone()

            if user:
                session["user_id"] = user[0]
                session["vards"] = user[1]
                return redirect("/home")

        elif mode == "register":
            vards = request.form.get("vards")
            uzvards = request.form.get("uzvards")

            cur.execute("""
                INSERT INTO lietotajs (vards, uzvards, epasts, parole, loma)
                VALUES (?, ?, ?, ?, 'skolens')
            """, (vards, uzvards, email, parole))

            db.commit()

            cur.execute(
                "SELECT id, vards FROM lietotajs WHERE epasts=?",
                (email,)
            )
            user = cur.fetchone()
            session["user_id"] = user[0]
            session["vards"] = user[1]
            return redirect("/home")

        db.close()

    return render_template("login.html")


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