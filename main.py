from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "secret123"  # nepieciešams flash ziņām

# Pagaidu lietotājs (piemēram)
USER_EMAIL = "tavs@epasts.lv"
USER_PASSWORD = "parole123"

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == USER_EMAIL and password == USER_PASSWORD:
            return "Veiksmīga pieslēgšanās!"
        else:
            flash("Nepareizs e-pasts vai parole")

    return render_template("login.html")

if __name__ == "__main__":
    app.run(debug=True)
