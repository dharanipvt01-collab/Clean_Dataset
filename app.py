
from flask import (
    Flask, render_template, request, send_file,
    session, redirect, url_for, flash
)
import pandas as pd
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "clean_dataset_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"csv", "xlsx"}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_dataset():
    filename = session.get("dataset_file")

    if not filename:
        return None

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(filepath):
        return None

    if filename.lower().endswith(".csv"):
        return pd.read_csv(filepath)

    return pd.read_excel(filepath)


@app.route("/")
def index():
    df = get_dataset()

    if df is None:
        return render_template("index.html")

    stats = {
        "rows": len(df),
        "columns": len(df.columns),
        "missing": int(df.isnull().sum().sum()),
        "duplicates": int(df.duplicated().sum())
    }

    preview = df.head(10).fillna("").to_dict(orient="records")

    return render_template(
        "index.html",
        stats=stats,
        columns=list(df.columns),
        preview=preview
    )


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        flash("Please select a dataset.")
        return redirect(url_for("index"))

    file = request.files["file"]

    if file.filename == "":
        flash("No file selected.")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only CSV and XLSX files are allowed.")
        return redirect(url_for("index"))

    original_name = secure_filename(file.filename)
    filename = str(uuid.uuid4()) + "_" + original_name

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    try:
        if filename.lower().endswith(".csv"):
            pd.read_csv(filepath)
        else:
            pd.read_excel(filepath)
    except Exception:
        os.remove(filepath)
        flash("Invalid or unreadable dataset.")
        return redirect(url_for("index"))

    session["dataset_file"] = filename
    session.pop("cleaned_file", None)

    flash("Dataset uploaded successfully!")
    return redirect(url_for("index"))


@app.route("/clean", methods=["POST"])
def clean():
    try:
        df = get_dataset()

        if df is None:
            flash("Upload a dataset first.")
            return redirect(url_for("index"))

        action = request.form.get("action")

        if action == "duplicates":
            df = df.drop_duplicates()

        elif action == "missing":
            method = request.form.get("method", "drop")

            if method == "drop":
                df = df.dropna()

            elif method == "mean":
                for col in df.select_dtypes(include="number").columns:
                    df[col] = df[col].fillna(df[col].mean())

            elif method == "median":
                for col in df.select_dtypes(include="number").columns:
                    df[col] = df[col].fillna(df[col].median())

            elif method == "mode":
                for col in df.columns:
                    if not df[col].mode().empty:
                        df[col] = df[col].fillna(df[col].mode()[0])

        else:
            flash("Invalid cleaning operation.")
            return redirect(url_for("index"))

        output_name = "cleaned_" + str(uuid.uuid4()) + ".csv"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)

        df.to_csv(output_path, index=False)

        session["cleaned_file"] = output_name

        flash("Dataset cleaned successfully!")

    except Exception as e:
        flash(f"Cleaning error: {str(e)}")

    return redirect(url_for("index"))


@app.route("/download")
def download():
    filename = session.get("cleaned_file")

    if not filename:
        flash("Please clean your dataset first.")
        return redirect(url_for("index"))

    filepath = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(filepath):
        flash("Cleaned file not found.")
        return redirect(url_for("index"))

    return send_file(filepath, as_attachment=True)


@app.route("/clear")
def clear():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
