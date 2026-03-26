import sys
import os
import uuid
import mimetypes
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv

workspace_root = Path(__file__).parent.parent
sys.path.insert(0, str(workspace_root))

load_dotenv(workspace_root / '.env')
load_dotenv(workspace_root / 'env', override=False)

import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from backend.models import db, User, Input, Report
from ml_pipeline.analyzer import analyze_content
from ml_pipeline.report_generator import generate_pdf_report
from ml_pipeline.summary_module import summarize_text
from ml_pipeline.ocr_module import extract_text_from_image
from ml_pipeline.document_module import extract_text_from_document
from ml_pipeline.url_module import fetch_and_extract_from_url

# -------------------------------
# APP INIT
# -------------------------------

app = Flask(__name__)
CORS(app)

# -------------------------------
# CONFIG (Use ENV in production)
# -------------------------------

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "mysql://root:root%40123@localhost/misinformation_db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = os.getenv("UPLOAD_FOLDER", "uploads")
app.config["REPORT_FOLDER"] = os.getenv("REPORT_FOLDER", "reports")


def resolve_workspace_path(path_value):
    if not path_value:
        return None

    path = Path(path_value)
    if not path.is_absolute():
        path = workspace_root / path
    return str(path.resolve())


app.config["UPLOAD_FOLDER"] = resolve_workspace_path(app.config["UPLOAD_FOLDER"])
app.config["REPORT_FOLDER"] = resolve_workspace_path(app.config["REPORT_FOLDER"])

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)

db.init_app(app)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "txt", "docx"}
MAX_FILE_SIZE_MB = 10
MIMETYPE_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

FACT_CHECK_FEEDS = [
    "https://news.google.com/rss/search?q=global+fact+check+misinformation+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=debunked+fake+news+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://www.snopes.com/feed/",
]

FAKE_NEWS_RELEVANCE_TERMS = (
    "fake",
    "fact check",
    "fact-check",
    "debunk",
    "misinformation",
    "hoax",
    "myth",
    "rumor",
)


# -------------------------------
# HELPERS
# -------------------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_filename(file):
    original_name = (file.filename or "").strip()
    guessed_extension = MIMETYPE_TO_EXTENSION.get(file.mimetype, "")

    if original_name and allowed_file(original_name):
        return original_name

    base_name = secure_filename(Path(original_name).stem) if original_name else "upload"
    extension = Path(original_name).suffix.lower() if original_name else guessed_extension

    if extension not in {f".{ext}" for ext in ALLOWED_EXTENSIONS}:
        guessed_from_type = mimetypes.guess_extension(file.mimetype or "") or guessed_extension
        extension = guessed_from_type if guessed_from_type else extension

    if extension not in {f".{ext}" for ext in ALLOWED_EXTENSIONS}:
        return None

    return f"{base_name or 'upload'}{extension}"


def validate_file(file):
    if not file:
        return False, "No file provided"

    normalized_name = normalize_filename(file)
    if not normalized_name:
        return False, "File type not allowed"

    file.seek(0, os.SEEK_END)
    size_mb = file.tell() / (1024 * 1024)
    file.seek(0)

    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"File exceeds {MAX_FILE_SIZE_MB}MB limit"

    return True, normalized_name


def get_user_from_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def resolve_saved_file_path(file_path):
    resolved = resolve_workspace_path(file_path)
    return resolved if resolved and os.path.exists(resolved) else file_path


def extract_text_for_input(input_record):
    if input_record.content_type == "text":
        return input_record.content or ""

    if input_record.content_type == "url":
        try:
            url_data = fetch_and_extract_from_url(input_record.content or "")
            return url_data.get("text", "")
        except Exception:
            return ""

    resolved_file_path = resolve_saved_file_path(input_record.file_path)

    if input_record.content_type == "image" and resolved_file_path and os.path.exists(resolved_file_path):
        try:
            return extract_text_from_image(resolved_file_path)
        except Exception:
            return ""

    if input_record.content_type == "document" and resolved_file_path and os.path.exists(resolved_file_path):
        try:
            return extract_text_from_document(resolved_file_path)
        except Exception:
            return ""

    return ""


def build_report_for_input(input_record, result):
    existing_report = Report.query.filter_by(input_id=input_record.id).first()
    existing_path = resolve_saved_file_path(existing_report.report_path) if existing_report else None
    if existing_report and existing_path and os.path.exists(existing_path):
        if existing_report.report_path != existing_path:
            existing_report.report_path = existing_path
            db.session.commit()
        return existing_report

    report_path = generate_pdf_report(result, input_record.id)

    report = Report(
        input_id=input_record.id,
        prediction=result["prediction"],
        confidence=result["confidence"],
        manipulation_score=result["manipulation_score"],
        report_path=report_path
    )

    db.session.add(report)
    db.session.commit()
    return report


def _safe_parse_datetime(date_text):
    if not date_text:
        return None
    try:
        dt = parsedate_to_datetime(date_text)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _strip_html_and_entities(raw_text):
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_feed_items(xml_text, source_label):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for item in root.findall(".//item"):
        title = _strip_html_and_entities(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        pub_date_text = (item.findtext("pubDate") or "").strip()
        description = _strip_html_and_entities(item.findtext("description") or "")

        if not title or not link:
            continue

        derived_source = source_label
        if " - " in title:
            title_part, source_part = title.rsplit(" - ", 1)
            if title_part.strip() and source_part.strip():
                title = title_part.strip()
                derived_source = source_part.strip()[:70]

        summary = description[:240] if description else f"Fact-check update: {title}"

        published_dt = _safe_parse_datetime(pub_date_text)
        items.append(
            {
                "title": title,
                "url": link,
                "source": derived_source,
                "summary": summary,
                "published_at": published_dt.isoformat() if published_dt else None,
                "sort_key": published_dt.timestamp() if published_dt else 0,
            }
        )

    return items


def fetch_top_fake_news(limit=8):
    combined = []
    seen_urls = set()

    for feed_url in FACT_CHECK_FEEDS:
        source_label = "Snopes" if "snopes.com" in feed_url else "Global Fact-Check Watch"
        try:
            response = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=10)
            response.raise_for_status()
            parsed_items = _extract_feed_items(response.text, source_label)
            for item in parsed_items:
                relevance_text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
                if not any(term in relevance_text for term in FAKE_NEWS_RELEVANCE_TERMS):
                    continue
                url = item["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                combined.append(item)
        except Exception:
            continue

    combined.sort(key=lambda x: x["sort_key"], reverse=True)
    trimmed = combined[:limit]

    for item in trimmed:
        item.pop("sort_key", None)

    return trimmed


# -------------------------------
# HOME
# -------------------------------

@app.route("/")
def home():
    return jsonify({
        "message": "Misinformation Analyzer Running",
        "status": "healthy"
    })


@app.route("/api/top-fake-news", methods=["GET"])
def top_fake_news():
    items = fetch_top_fake_news(limit=8)
    return jsonify(
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "count": len(items),
            "items": items,
        }
    )


# -------------------------------
# REGISTER
# -------------------------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}

    if not all(k in data for k in ["email", "username", "password"]):
        return jsonify({"error": "Missing required fields"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 400

    user = User(
        email=data["email"],
        username=data["username"],
        password=generate_password_hash(data["password"]),
        role="user",
    )

    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "User registered"})


# -------------------------------
# LOGIN
# -------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}

    user = User.query.filter_by(email=data.get("email")).first()

    if not user or not check_password_hash(user.password, data.get("password", "")):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "message": "Login successful",
        "token": str(user.id),  # Replace with JWT in production
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role
        }
    })


# -------------------------------
# ANALYZE
# -------------------------------

@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        payload = request.get_json(silent=True) if request.is_json else None
        request_data = payload or request.form

        user_id = request_data.get("user_id") or get_user_from_token()
        content_type = request_data.get("content_type")
        content = request_data.get("content", "")
        uploaded_file = request.files.get("file")

        # -------------------------------
        # VALIDATION
        # -------------------------------

        if not user_id:
            return jsonify({"error": "user_id required"}), 400

        try:
            user_id = int(user_id)
        except:
            return jsonify({"error": "Invalid user_id"}), 400

        if content_type not in ["text", "url", "image", "document"]:
            return jsonify({"error": "Invalid content_type"}), 400

        file_path = None

        # -------------------------------
        # FILE HANDLING
        # -------------------------------

        if uploaded_file:
            is_valid, validated_name = validate_file(uploaded_file)
            if not is_valid:
                return jsonify({"error": validated_name}), 400

            filename = secure_filename(validated_name)
            filename = f"{uuid.uuid4().hex}_{filename}"

            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            uploaded_file.save(file_path)

        # -------------------------------
        # SAVE INPUT
        # -------------------------------

        input_record = Input(
            user_id=user_id,
            content_type=content_type,
            content=content,
            file_path=file_path
        )

        db.session.add(input_record)
        db.session.commit()

        # -------------------------------
        # ANALYSIS
        # -------------------------------

        result = analyze_content(content_type, content, file_path)

        # -------------------------------
        # REPORT GENERATION
        # -------------------------------

        return jsonify({
            "input_id": input_record.id,
            "result": result,
            "report_id": None,
            "report_url": None
        })

    except Exception as e:
        db.session.rollback()
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/api/input/<int:input_id>/summary", methods=["POST"])
def generate_summary(input_id):
    input_record = db.session.get(Input, input_id)

    if not input_record:
        return jsonify({"error": "Input not found"}), 404

    text = extract_text_for_input(input_record) or input_record.content or ""
    summary = summarize_text(text)

    return jsonify({
        "input_id": input_id,
        "summary": summary,
        "extracted_text": text,
    })


@app.route("/api/input/<int:input_id>/report", methods=["POST"])
def generate_report(input_id):
    input_record = db.session.get(Input, input_id)

    if not input_record:
        return jsonify({"error": "Input not found"}), 404

    result = analyze_content(
        input_record.content_type,
        input_record.content,
        resolve_saved_file_path(input_record.file_path)
    )

    report = build_report_for_input(input_record, result)

    return jsonify({
        "report_id": report.id,
        "report_url": f"/api/report/{report.id}"
    })


# -------------------------------
# GET REPORT
# -------------------------------

@app.route("/api/report/<int:report_id>")
def report(report_id):
    report = db.session.get(Report, report_id)

    report_path = resolve_saved_file_path(report.report_path) if report else None
    if report and report_path and report.report_path != report_path:
        report.report_path = report_path
        db.session.commit()

    if not report or not report_path or not os.path.exists(report_path):
        return jsonify({"error": "Report not found"}), 404

    return send_file(report_path, as_attachment=True)


# -------------------------------
# ADMIN INPUTS
# -------------------------------

@app.route("/api/admin/inputs")
def admin_inputs():
    inputs = Input.query.all()

    return jsonify([
        {
            "id": i.id,
            "user_id": i.user_id,
            "content_type": i.content_type,
            "created_at": i.created_at
        }
        for i in inputs
    ])


# -------------------------------
# ADMIN REPORTS
# -------------------------------

@app.route("/api/admin/reports")
def admin_reports():
    reports = Report.query.all()

    return jsonify([
        {
            "id": r.id,
            "prediction": r.prediction,
            "confidence": r.confidence,
            "created_at": r.created_at
        }
        for r in reports
    ])


# -------------------------------
# RUN
# -------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(
        debug=True,
        host=os.getenv("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_RUN_PORT", "5000")),
    )
