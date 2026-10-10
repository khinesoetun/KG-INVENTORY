import os

from flask import (
    Blueprint, render_template, session,
    request, redirect, url_for, flash,
    current_app
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from inventory.auth.routes import login_required, admin_required
from database import get_db

settings_bp = Blueprint("settings", __name__)

def allowed_profile_photo(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_PROFILE_PHOTO_SIZE = 2 * 1024 * 1024

@settings_bp.route("/settings")
@login_required
def settings():
    users = []
    profile_photo = None

    db = get_db()

    try:
        user = db.execute(
            "SELECT profile_photo FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if user:
            profile_photo = user["profile_photo"]

        if session.get("role") == "admin":
            users = db.execute(
                """
                SELECT id, username, role
                FROM users
                ORDER BY id
                """
            ).fetchall()

    finally:
        db.close()

    return render_template(
        "settings/settings.html",
        users=users,
        profile_photo=profile_photo
    )
#============================================================================
#=========== add user ======================================================
@settings_bp.route("/settings/users/create", methods=["POST"])
@login_required
@admin_required
def create_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "staff")

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("settings.settings"))

    if role not in ("admin", "staff"):
        flash("Invalid role.", "error")
        return redirect(url_for("settings.settings"))

    db = get_db()
    try:
        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if existing_user:
            flash("Username already exists.", "error")
            return redirect(url_for("settings.settings"))

        db.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, generate_password_hash(password), role)
        )
        db.commit()

    finally:
        db.close()

    flash("User created successfully.", "success")
    return redirect(url_for("settings.settings"))
#============================================================================================
#===========  update user   ================================================================

@settings_bp.route("/settings/users/update", methods=["POST"])
@login_required
@admin_required
def update_user():
    user_id = request.form.get("user_id", type=int)
    username = request.form.get("username", "").strip()
    role = request.form.get("role", "")

    if not user_id or not username:
        flash("Username is required.", "error")
        return redirect(url_for("settings.settings"))

    if role not in ("admin", "staff"):
        flash("Invalid role.", "error")
        return redirect(url_for("settings.settings"))

    db = get_db()
    try:
        target_user = db.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not target_user:
            flash("User not found.", "error")
            return redirect(url_for("settings.settings"))

        existing_user = db.execute(
            "SELECT id FROM users WHERE username = ? AND id != ?",
            (username, user_id)
        ).fetchone()

        if existing_user:
            flash("Username already exists.", "error")
            return redirect(url_for("settings.settings"))

        if (
            target_user["id"] == session["user_id"]
            and target_user["role"] == "admin"
            and role != "admin"
        ):
            flash("You cannot demote your own admin account.", "error")
            return redirect(url_for("settings.settings"))
        
        if target_user["role"] == "admin" and role != "admin":
            admin_count = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin'"
            ).fetchone()[0]

            if admin_count <= 1:
                flash("Cannot demote the last admin account.", "error")
                return redirect(url_for("settings.settings"))

        db.execute(
            "UPDATE users SET username = ?, role = ? WHERE id = ?",
            (username, role, user_id)
        )
        db.commit()

        if target_user["id"] == session["user_id"]:
            session["username"] = username
            session["role"] = role

    finally:
        db.close()

    flash("User updated successfully.", "success")
    return redirect(url_for("settings.settings"))
#============================================================================================
#=================  reset password      =====================================================
@settings_bp.route("/settings/users/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_user_password():
    user_id = request.form.get("user_id", type=int)
    new_password = request.form.get("new_password", "")

    if not user_id or len(new_password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("settings.settings"))

    db = get_db()

    try:
        user = db.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("settings.settings"))

        password_hash = generate_password_hash(new_password)

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id)
        )

        db.commit()

    finally:
        db.close()

    flash("User password reset successfully.", "success")
    return redirect(url_for("settings.settings"))
#=========================================================================================
#===========  delete account            ==================================================
@settings_bp.route("/settings/users/delete", methods=["POST"])
@login_required
@admin_required
def delete_user():
    user_id = request.form.get("user_id", type=int)

    if not user_id:
        flash("Invalid user.", "error")
        return redirect(url_for("settings.settings"))

    # Prevent deleting your own account
    if user_id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("settings.settings"))

    db = get_db()

    try:
        target_user = db.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not target_user:
            flash("User not found.", "error")
            return redirect(url_for("settings.settings"))

        # Prevent deleting the last admin
        if target_user["role"] == "admin":
            admin_count = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin'"
            ).fetchone()[0]

            if admin_count <= 1:
                flash("Cannot delete the last admin account.", "error")
                return redirect(url_for("settings.settings"))

        db.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,)
        )
        db.commit()

    finally:
        db.close()

    flash("User deleted successfully.", "success")
    return redirect(url_for("settings.settings"))

# =========================================================
# Change own password
# =========================================================

@settings_bp.route("/settings/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        flash("All password fields are required.", "error")
        return redirect(url_for("settings.settings"))

    if len(new_password) < 8:
        flash("New password must be at least 8 characters.", "error")
        return redirect(url_for("settings.settings"))

    if new_password != confirm_password:
        flash("New passwords do not match.", "error")
        return redirect(url_for("settings.settings"))

    db = get_db()

    try:
        user = db.execute(
            "SELECT id, password_hash FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("settings.settings"))

        if not check_password_hash(
            user["password_hash"], current_password
        ):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("settings.settings"))

        password_hash = generate_password_hash(new_password)

        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, session["user_id"])
        )
        db.commit()

    finally:
        db.close()

    flash("Password changed successfully.", "success")
    return redirect(url_for("settings.settings"))
# =========================================================
# Upload profile photo
# =========================================================

@settings_bp.route("/settings/profile-photo", methods=["POST"])
@login_required
def upload_profile_photo():
    photo = request.files.get("profile_photo")

    if not photo or not photo.filename:
        flash("Please choose a photo.", "error")
        return redirect(url_for("settings.settings"))

    if not allowed_profile_photo(photo.filename):
        flash("Only JPG, JPEG, PNG and WEBP images are allowed.", "error")
        return redirect(url_for("settings.settings"))

    photo_data = photo.read(MAX_PROFILE_PHOTO_SIZE + 1)

    if not photo_data:
        flash("The selected file is empty.", "error")
        return redirect(url_for("settings.settings"))

    if len(photo_data) > MAX_PROFILE_PHOTO_SIZE:
        flash("Profile photo must be 2 MB or smaller.", "error")
        return redirect(url_for("settings.settings"))

    # Check that the file is a real image
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(BytesIO(photo_data))
        image.verify()
    except (UnidentifiedImageError, OSError):
        flash("The selected file is not a valid image.", "error")
        return redirect(url_for("settings.settings"))

    filename = secure_filename(photo.filename)

    if not filename:
        flash("Invalid filename.", "error")
        return redirect(url_for("settings.settings"))

    import uuid

    extension = filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{extension}"

    upload_folder = os.path.join(
        current_app.static_folder,
        "uploads",
        "profiles"
    )
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)
    relative_path = f"uploads/profiles/{unique_filename}"

    db = get_db()

    try:
        user = db.execute(
            "SELECT profile_photo FROM users WHERE id = ?",
            (session["user_id"],)
        ).fetchone()

        if not user:
            flash("User not found.", "error")
            return redirect(url_for("settings.settings"))

        # Save the new photo
        with open(file_path, "wb") as f:
            f.write(photo_data)

        # Update the database
        db.execute(
            "UPDATE users SET profile_photo = ? WHERE id = ?",
            (relative_path, session["user_id"])
        )
        db.commit()

    except Exception:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise

    finally:
        db.close()

    # Delete the old photo only after a successful commit
    old_photo = user["profile_photo"]

    if old_photo and old_photo != relative_path:
        try:
            delete_old_profile_photo(old_photo, upload_folder)
        except OSError:
            current_app.logger.exception(
                "Failed to delete old profile photo."
            )

    flash("Profile photo updated successfully.", "success")
    return redirect(url_for("settings.settings"))
#================================================================================
def delete_old_profile_photo(relative_path, upload_folder):
    if not relative_path:
        return

    # Only delete files from the profile-photo folder
    prefix = "uploads/profiles/"

    if not relative_path.startswith(prefix):
        return

    filename = relative_path[len(prefix):]

    # Reject empty names or nested paths
    if not filename or os.path.basename(filename) != filename:
        return

    upload_folder = os.path.realpath(upload_folder)
    old_file = os.path.realpath(
        os.path.join(upload_folder, filename)
    )

    # Make sure the target stays inside the profile-photo folder
    if os.path.commonpath([upload_folder, old_file]) != upload_folder:
        return

    if os.path.isfile(old_file):
        os.remove(old_file)