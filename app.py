import os
import json
import re
import secrets
import tempfile

from flask import Flask, render_template, request, abort, send_from_directory, redirect, url_for, Response
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
DOOR_EDITOR_PASSWORD = os.getenv("DOOR_EDITOR_PASSWORD", "")
DOOR_EDITOR_PASSWORD_PATTERN = re.compile(r"^.{8,}$")
ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.getenv(
        "ALLOWED_HOSTS",
        "princessevelyn.com,www.princessevelyn.com,localhost,127.0.0.1",
    ).split(",")
    if h.strip()
}

CATEGORY_LABELS = {
    "good": "good",
    "neutral": "neutral",
    "bad": "bad",
    "probablyGood": "probably good",
    "probablyBad": "probably bad",
}

CATEGORY_TONES = {
    "good": "good",
    "neutral": "neutral",
    "bad": "bad",
    "probablyGood": "uncertain-good",
    "probablyBad": "uncertain-bad",
}

EDITOR_CATEGORIES = [
    {
        "key": "good",
        "label": "Good",
        "tone": "good",
    },
    {
        "key": "neutral",
        "label": "Neutral",
        "tone": "neutral",
    },
    {
        "key": "bad",
        "label": "Bad",
        "tone": "bad",
    },
    {
        "key": "probablyGood",
        "label": "Probably Good",
        "tone": "uncertain-good",
    },
    {
        "key": "probablyBad",
        "label": "Probably Bad",
        "tone": "uncertain-bad",
    },
]

NON_WORD_PATTERN = re.compile(r"[^\w]+")
SPACE_PATTERN = re.compile(r"\s+")
APOSTROPHE_PATTERN = re.compile(r"['’]")


def get_request_host():
    host = request.host or ""
    return host.split(":")[0].lower()


def is_safe_host(host):
    return host in ALLOWED_HOSTS


def normalize_hint(value):
    lowered = value.casefold()
    without_apostrophes = APOSTROPHE_PATTERN.sub("", lowered)
    without_punctuation = NON_WORD_PATTERN.sub(" ", without_apostrophes)
    return SPACE_PATTERN.sub(" ", without_punctuation).strip()


def get_door_data_path(static_folder):
    return Path(static_folder) / "door-data.json"


def load_door_data(static_folder):
    with get_door_data_path(static_folder).open(encoding="utf-8") as data_file:
        return json.load(data_file)


def load_door_hints(static_folder):
    data = load_door_data(static_folder)

    neutral_hints = data.get("neutral", data.get("neutralHints", []))
    bad_hints = data.get("bad", data.get("badHints", []))
    categorized_hints = [
        ("good", data.get("good", [])),
        ("neutral", neutral_hints),
        ("bad", bad_hints),
        ("probablyGood", data.get("inconclusive", {}).get("probablyGood", [])),
        ("probablyBad", data.get("inconclusive", {}).get("probablyBad", [])),
    ]

    hints = []
    seen = set()

    def append_hint(phrase, category, label, tone, count_text=None):
        if not isinstance(phrase, str):
            return

        normalized = normalize_hint(phrase)
        signature = (category, phrase, count_text)
        if signature in seen:
            return

        seen.add(signature)
        hint = {
            "phrase": phrase,
            "category": category,
            "tone": tone,
            "normalized": normalized,
        }
        if label is not None:
            hint["label"] = label
        if count_text is not None:
            hint["count_text"] = count_text
        hints.append(hint)

    for category, phrases in categorized_hints:
        for phrase in phrases:
            append_hint(
                phrase,
                category,
                CATEGORY_LABELS[category],
                CATEGORY_TONES[category],
            )

    for entry in data.get("uncertain", []):
        if not isinstance(entry, dict):
            continue

        good_count = entry.get("good", 0)
        bad_count = entry.get("bad", 0)
        append_hint(
            entry.get("hint"),
            "uncertain",
            None,
            "neutral",
            f"{good_count} / {bad_count}",
        )

    return hints


def get_editor_values(data, key):
    if key == "neutral":
        return data.get("neutral", data.get("neutralHints", []))
    if key == "bad":
        return data.get("bad", data.get("badHints", []))
    if key in {"probablyGood", "probablyBad"}:
        return data.get("inconclusive", {}).get(key, [])
    return data.get(key, [])


def get_editor_categories(data):
    categories = []
    for category in EDITOR_CATEGORIES:
        values = get_editor_values(data, category["key"])
        categories.append({**category, "values": values, "count": len(values)})
    return categories


def parse_count(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def get_uncertain_entries(data):
    entries = []
    for entry in data.get("uncertain", []):
        if not isinstance(entry, dict):
            continue

        hint = entry.get("hint")
        if not isinstance(hint, str) or not hint.strip():
            continue

        entries.append(
            {
                "hint": hint,
                "good": parse_count(entry.get("good", 0)),
                "bad": parse_count(entry.get("bad", 0)),
            }
        )
    return entries


def collect_editor_values(form, key):
    return [
        value.strip()
        for value in form.getlist(key)
        if value.strip()
    ]


def collect_uncertain_entries(form):
    hints = form.getlist("uncertain_hint")
    good_counts = form.getlist("uncertain_good")
    bad_counts = form.getlist("uncertain_bad")

    entries = []
    for index, hint in enumerate(hints):
        hint = hint.strip()
        if not hint:
            continue

        good_count = good_counts[index] if index < len(good_counts) else 0
        bad_count = bad_counts[index] if index < len(bad_counts) else 0
        entries.append(
            {
                "hint": hint,
                "good": parse_count(good_count),
                "bad": parse_count(bad_count),
            }
        )
    return entries


def build_door_data_from_form(form, existing_data=None):
    data = {
        "good": collect_editor_values(form, "good"),
        "neutral": collect_editor_values(form, "neutral"),
        "bad": collect_editor_values(form, "bad"),
        "inconclusive": {
            "probablyGood": collect_editor_values(form, "probablyGood"),
            "probablyBad": collect_editor_values(form, "probablyBad"),
        },
    }
    if form.get("has_uncertain") == "1":
        data["uncertain"] = collect_uncertain_entries(form)
    elif existing_data and "uncertain" in existing_data:
        data["uncertain"] = get_uncertain_entries(existing_data)
    return data


def write_door_data(static_folder, data):
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    data_path = get_door_data_path(static_folder)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=data_path.parent,
            encoding="utf-8",
            prefix=f".{data_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(rendered)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        temp_path.replace(data_path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def render_plain_text_door_data(data):
    sections = [
        ("Good", data.get("good", [])),
        ("Neutral", data.get("neutral", data.get("neutralHints", []))),
        ("Bad", data.get("bad", data.get("badHints", []))),
        (
            "Inconclusive due to not enough data (but probably good)",
            data.get("inconclusive", {}).get("probablyGood", []),
        ),
        (
            "Inconclusive due to not enough data (but probably bad)",
            data.get("inconclusive", {}).get("probablyBad", []),
        ),
    ]

    lines = []
    for title, phrases in sections:
        lines.append(f"{title}:")
        lines.extend(phrases)
        lines.append("")
    uncertain = data.get("uncertain", [])
    if uncertain:
        lines.append("Uncertain:")
        for entry in uncertain:
            if not isinstance(entry, dict) or not entry.get("hint"):
                continue
            good_count = entry.get("good", 0)
            bad_count = entry.get("bad", 0)
            lines.append(f"{entry['hint']} ({good_count} / {bad_count})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def find_door_hint_matches(hints, query):
    normalized_query = normalize_hint(query)
    if not normalized_query:
        return "", []

    matches = [
        hint
        for hint in hints
        if normalized_query in hint["normalized"]
    ]
    return normalized_query, matches


def is_door_editor_password(value):
    if not is_door_editor_configured():
        return False
    return secrets.compare_digest(value or "", DOOR_EDITOR_PASSWORD)


def is_door_editor_configured():
    return bool(DOOR_EDITOR_PASSWORD_PATTERN.fullmatch(DOOR_EDITOR_PASSWORD))


def create_app():
    app = Flask(__name__)
    if FLASK_SECRET_KEY:
        app.config["SECRET_KEY"] = FLASK_SECRET_KEY
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def enforce_host_check():
        if ALLOWED_HOSTS and not is_safe_host(get_request_host()):
            abort(400)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'none'; "
            "form-action 'self'; "
            "base-uri 'self'"
        )
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/healthz")
    def healthz():
        return "ok", 200

    @app.get("/favicon.ico")
    def favicon():
        return send_from_directory(
            app.static_folder, "favicon.svg", mimetype="image/svg+xml"
        )

    @app.get("/dog")
    def dog():
        dog_url = "https://placedog.net/720/520?random"
        return render_template("dog.html", dog_url=dog_url)

    @app.get("/cat")
    def cat():
        return render_template("cat.html")

    @app.get("/door/classifier")
    def door_classifier():
        query = request.args.get("hint", "")
        hints = load_door_hints(app.static_folder)
        preview_image = url_for(
            "static",
            filename="img/door-classifier-preview.jpeg",
            _external=True,
        )
        normalized_query, matches = find_door_hint_matches(
            hints,
            query,
        )
        return render_template(
            "door_classifier.html",
            query=query,
            normalized_query=normalized_query,
            matches=matches,
            hints=hints,
            canonical_url=url_for("door_classifier", _external=True),
            preview_image=preview_image,
        )

    @app.route("/door/classifier/edit", methods=["GET", "POST"])
    def door_classifier_edit():
        message = ""
        error = ""
        editor_password = ""
        posted_password = request.form.get("editor_password", "")

        if not is_door_editor_configured():
            return render_template(
                "door_editor.html",
                locked=True,
                configured=False,
                error="Set DOOR_EDITOR_PASSWORD to at least 8 characters to enable editing.",
            )

        if request.method == "POST" and request.form.get("action") == "unlock":
            if is_door_editor_password(posted_password):
                editor_password = posted_password
                message = "Unlocked."
            else:
                error = "That password did not work."
        elif request.method == "POST" and request.form.get("action") == "save":
            if is_door_editor_password(posted_password):
                editor_password = posted_password
                data = build_door_data_from_form(
                    request.form,
                    existing_data=load_door_data(app.static_folder),
                )
                write_door_data(app.static_folder, data)
                message = "Saved."
            else:
                error = "Please unlock the editor before saving."

        if not is_door_editor_password(editor_password):
            return render_template(
                "door_editor.html",
                locked=True,
                configured=True,
                error=error,
            )

        data = load_door_data(app.static_folder)
        return render_template(
            "door_editor.html",
            locked=False,
            categories=get_editor_categories(data),
            uncertain_entries=get_uncertain_entries(data),
            editor_password=editor_password,
            message=message,
            error=error,
            classifier_url=url_for("door_classifier"),
        )

    @app.post("/door/classifier/export")
    def door_classifier_export():
        posted_password = request.form.get("editor_password", "")
        if not is_door_editor_password(posted_password):
            abort(403)

        data = build_door_data_from_form(
            request.form,
            existing_data=load_door_data(app.static_folder),
        )
        exported = render_plain_text_door_data(data)
        return Response(
            exported,
            mimetype="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=door-data.txt",
            },
        )

    @app.get("/robots.txt")
    def robotstxt():
        return send_from_directory(
            app.static_folder, "robots.txt", mimetype="text/plain"
        )

    @app.get("/license/pel-1")
    def license1():
        return send_from_directory(
            app.static_folder, "PEL-1.md", mimetype="text/plain"
        )        

    @app.get("/videos/1")
    def video1():
        return send_from_directory(
            Path(app.static_folder) / "videos", "recording1.mp4", mimetype="video/mp4"
        )        

    @app.get("/videos/2")
    def video2():
        return send_from_directory(
            Path(app.static_folder) / "videos", "recording2.mp4", mimetype="video/mp4"
        )  

    @app.get("/forbidden")
    def test_403():
        abort(403)

    @app.get("/error")
    def test_500():
        abort(500)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("500.html"), 500

    return app
