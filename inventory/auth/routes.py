import os

from flask import Blueprint, render_template, request, redirect, url_for, session, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db
from functools import wraps

auth_bp = Blueprint("auth",__name__)
def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        return view(*args, **kwargs)

    return wrapped_view


def create_initial_admin():
    username = os.getenv("KG_INVENTORY_ADMIN_USERNAME")
    password = os.getenv("KG_INVENTORY_ADMIN_PASSWORD")

    if not username or not password:
        raise RuntimeError("Admin credentials are missing from .env")

    db = get_db()

    try:
        existing_admin = db.execute(
            "SELECT id FROM users WHERE role = ? LIMIT 1",
            ("admin",)
        ).fetchone()

        if existing_admin:
            return

        db.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                "admin"
            )
        )
        db.commit()

    finally:
        db.close()

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))

        if session.get("role") != "admin":
            return redirect(url_for("sales.sales"))

        return view(*args, **kwargs)

    return wrapped_view

#==================================================================================
#============== LOGIN ROUTE     ===================================================
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth/login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    db = get_db()

    try:
        user = db.execute(
            """
            SELECT id, username, password_hash, role
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()
    finally:
        db.close()

    if not user or not check_password_hash(
        user["password_hash"], password
    ):
        response = make_response(
            '<p class="text-sm">Username or password is incorrect.</p>',
            401
        )
        response.headers["HX-Retarget"] = "#login-error"
        response.headers["HX-Reswap"] = "innerHTML"
        return response

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]

    response = make_response("", 204)
    response.headers["HX-Redirect"] = url_for("dashboard.home")
    return response
#====================================================================================
#===============    logout route        =============================================
@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("auth.login"))