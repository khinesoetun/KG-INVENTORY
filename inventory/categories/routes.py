from flask import Blueprint, render_template, request, redirect, url_for
from database import get_db
import sqlite3

category_bp = Blueprint("category", __name__)


@category_bp.route("/categories")
def categories():
    db = get_db()
    categories = db.execute("""
     SELECT
    categories.id,
    categories.name,
    categories.photo,
    COUNT(products.id) AS product_count
    FROM categories
    LEFT JOIN products
    ON categories.id = products.category_id
    GROUP BY categories.id
    ORDER BY categories.name
    """).fetchall()
    db.close()

    return render_template("categories/categories.html", categories=categories)


# ===================================================================================
# ===============        ADD CATEGORIES      ========================================
@category_bp.route("/category/add", methods=["POST", "GET"])
def add_category():
    message = None
    message_type = None
    name = request.form.get("name")
    photo = request.files.get("photo")
    photo_name = photo.filename if photo else None
    print("photo", photo)
    print("Filename:", photo_name)
    if not name:
        return "Category name is required"
    if photo and photo.filename:
        photo.save("static/uploads/categories-photo/" + photo_name)
    try:
        db = get_db()
        db.execute(
            "INSERT INTO categories (name,photo) VALUES (?,?)", (name, photo_name)
        )
        db.commit()
        message = "Category added successfully."
        message_type = "success"
    except sqlite3.IntegrityError:
        message = "Category name is already exists."
        message_type = "error"

    categories = db.execute("""
            SELECT
                categories.id,
                categories.name,
                categories.photo,
                COUNT(products.id) AS product_count
            FROM categories
            LEFT JOIN products
            ON categories.id = products.category_id
            GROUP BY categories.id
            ORDER BY categories.name
        """).fetchall()
    db.close()
    if request.headers.get("HX-Request"):
        return render_template(
            "categories/_category_cards.html", categories=categories
        ) + render_template(
            "categories/_message.html", message=message, message_type=message_type
        )

    return render_template(
        "categories/_message.html", message=message, message_type=message_type
    )


# =========================================================================================
# ===============        VIEW CATOGORIES     ==============================================
@category_bp.route("/categories/<int:id>")
def view_category(id):
    db = get_db()
    category = db.execute("SELECT * FROM categories WHERE id = ?", (id,)).fetchone()
    if not category:
        db.close()
        return "Category is not found."
    products = db.execute(
        "SELECT * FROM products WHERE category_id = ?", (id,)
    ).fetchall()
    db.close()
    return render_template(
        "categories/category_view.html", category=category, products=products
    )


# ==========================================================================================
# ==================     EDIT CATEGORY           ===========================================
@category_bp.route("/categories/<int:id>/edit", methods=["GET", "POST"])
def edit_category(id):
    message = None
    message_type = None
    db = get_db()
    category = db.execute("SELECT * FROM categories WHERE id= ?", (id,)).fetchone()
    if not category:
        return "Category not found"
    if request.method == "GET":
        return render_template("categories/_edit_form.html", category=category)

    if request.method == "POST":
        try:
            name = request.form.get("name")
            photo = request.files.get("photo")
            print("name:", name)
            print("photo", photo)
            photo_name = category["photo"]
            if photo and photo.filename:
                photo_name = photo.filename
                photo.save("static/uploads/categories-photo/" + photo.filename)
            db.execute(
                "UPDATE categories SET name = ? ,photo = ? WHERE id = ?",
                (name, photo_name, id),
            )
            db.commit()
            message = "Change category name is successfully."
            message_type = "success"
        except sqlite3.IntegrityError:
            message = "Category name is already exists."
            message_type = "error"
    category = db.execute(
        """
    SELECT
        categories.id,
        categories.name,
        categories.photo,
        COUNT(products.id) AS product_count
    FROM categories
    LEFT JOIN products
    ON categories.id = products.category_id
    WHERE categories.id = ?
    GROUP BY categories.id
    """,
        (id,),
    ).fetchone()
    categories = db.execute("""
        SELECT 
        categories.id,
        categories.name,
        categories.photo,
        COUNT(products.id) AS product_count
        FROM categories
        LEFT JOIN products
        ON categories.id = products.category_id
        GROUP BY categories.id
        ORDER BY categories.name
    """).fetchall()
    db.close()

    if request.headers.get("HX-Request"):
        return render_template(
            "categories/_edit_category_card.html", category=category
        ) + render_template(
            "categories/_edit_message.html", message=message, message_type=message_type
        )
    return render_template("categories/_category_cards.html", categories=categories)


# =================================================================================================
# =====================      CATEGORIES SEARCH       ==============================================
@category_bp.route("/categories/search")
def search_categories():
    query = request.args.get("q", "")
    db = get_db()

    categories = db.execute(
        """
        SELECT
            categories.id,
            categories.name,
            categories.photo,
            COUNT(products.id) AS product_count
        FROM categories
        LEFT JOIN products
        ON categories.id = products.category_id
        WHERE categories.name LIKE ?
        GROUP BY categories.id
        ORDER BY categories.name
    """,
        (f"%{query}%",),
    ).fetchall()
    db.close()
    return render_template("categories/_category_cards.html", categories=categories)


# =============================================================================================
# ===================        DELETE CATEGORIES       ==========================================
@category_bp.route("/categories/<int:id>/delete", methods=["POST"])
def delete_category(id):
    db = get_db()
    category = db.execute("SELECT * FROM categories WHERE id = ?", (id,)).fetchone()
    if not category:
        return "category not found."
    db.execute("DELETE FROM categories WHERE id = ?", (id,))
    db.commit()
    categories = db.execute("""
         SELECT 
         categories.id,
         categories.name,
         categories.photo,
         COUNT(products.id) AS product_count
         FROM categories
         LEFT JOIN products
         ON categories.id = products.category_id
         GROUP BY categories.id
         ORDER BY categories.name 
         """).fetchall()
    db.close()
    return render_template("categories/_category_cards.html", categories=categories)


# =====================================================================================
# ==============         delete comfirm route    ======================================
@category_bp.route("/categories/<int:id>/delete-confirm")
def delete_confirm(id):
    return render_template("categories/_delete_confirm.html", id=id)
