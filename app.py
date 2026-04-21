import os

from flask import Flask, render_template, request, abort, send_from_directory, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

load_dotenv()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.getenv(
        "ALLOWED_HOSTS",
        "princessevelyn.com,www.princessevelyn.com,localhost,127.0.0.1",
    ).split(",")
    if h.strip()
}


def get_request_host():
    host = request.host or ""
    return host.split(":")[0].lower()


def is_safe_host(host):
    return host in ALLOWED_HOSTS


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

    @app.get("/license/pel-s1")
    def license1():
        return send_from_directory(
            app.static_folder, "PEL-S1.md", mimetype="text/plain"
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
