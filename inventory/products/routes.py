from flask import Blueprint, render_template, request, url_for, redirect, make_response
from database import get_db, UPLOADS_PATH
import sqlite3
import os

product_bp = Blueprint("product", __name__)


@product_bp.route("/products", methods=["GET", "POST"])
def products():
    message_type = None
    message = None
    product_id = None
    error = False
    db = get_db()
    if request.method == "POST":
        try:
            name = request.form["name"]
            category_id = request.form["category_id"]
            price = request.form["price"]
            cost_price = request.form["cost_price"]
            stock = request.form["stock"]
            photo = request.files["photo"]
            photo.save(os.path.join(UPLOADS_PATH, photo.filename))
            cursor = db.execute(
                """
                     INSERT INTO products(name,category_id,cost_price,price,stock,photo)
                     VALUES (?,?,?,?,?,?)
                    """,
                (name, category_id, cost_price, price, stock, photo.filename),
            )
            db.commit()
            product_id = cursor.lastrowid
            message = "Product addede successfully"
            message_type = "success"
        except sqlite3.IntegrityError:

            message = "Product name already exists."
            message_type = "error"

    product = db.execute(
        """
    SELECT 
        products.id,
        products.name,
        categories.name As category,
        products.price,
        products.cost_price,
        products.stock,
        products.photo
    FROM products
    JOIN categories
    ON products.category_id = categories.id
    WHERE products.id =?
    """,
        (product_id,),
    ).fetchone()

    products = db.execute("""
    SELECT 
        products.id,
        products.name,
        categories.name AS category,
        products.price,
        products.cost_price,
        products.stock,
        products.photo
    FROM products
    JOIN categories
    ON products.category_id = categories.id
""").fetchall()

    categories = db.execute("""
    SELECT id, name
    FROM categories
    ORDER BY name
    """).fetchall()
    db.close()
    if request.headers.get("HX-Request"):
        if product:
            response = make_response(
                render_template("products/add_product_row.html", product=product)
                + render_template(
                    "products/_product_message.html",
                    message=message,
                    message_type=message_type,
                )
            )

            return response

        return render_template(
            "products/_product_message.html", message=message, message_type=message_type
        )

    return render_template(
        "products/products.html", products=products, categories=categories
    )


# ===================================================================================================
# ==================         DELETE ROUTE        ====================================================
@product_bp.route("/products/<int:id>/delete", methods=["POST"])
def delete_product(id):

    db = get_db()
    print(id)
    db.execute("DELETE FROM products WHERE id = ?", (id,))
    db.commit()
    products = db.execute("""
        SELECT
            products.id,
            products.name,
            categories.name AS category,
            products.price,
            products.cost_price,
            products.stock,
            products.photo
        FROM products
        JOIN categories
        ON products.category_id = categories.id
    """).fetchall()

    db.close()
    return render_template("products/_product_table.html", products=products)


# ============================================================================================
# ===================        EDIT ROUTE          ================================@product_bp.route("/products/<int:id>/edit", methods=["GET", "POST"])
@product_bp.route("/products/<int:id>/edit", methods=["GET", "POST"])
def edit_products(id):
    message = None
    message_type = None
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (id,)).fetchone()
    categories = db.execute(
        "SELECT id , name FROM categories ORDER BY name "
    ).fetchall()
    if request.method == "GET":
        db.close()
        return render_template(
            "products/_edit_form.html", product=product, categories=categories
        )

    if request.method == "POST":
        try:
            name = request.form["name"]
            category_id = request.form["category_id"]
            price = request.form["price"]
            cost_price = request.form["cost_price"]
            stock = request.form["stock"]
            photo = request.files.get("photo")
            photo_name = product["photo"]
            if photo and photo.filename:
                photo.save(os.path.join(UPLOADS_PATH, photo.filename))
                photo_name = photo.filename

            db.execute(
                """
                UPDATE products
                SET name = ?, category_id = ?,cost_price=?, price = ?,stock = ?,photo = ?
                WHERE id = ?
                """,
                (name, category_id, cost_price, price, stock, photo_name, id),
            )

            db.commit()
            message = "Product updated successfully."
            message_type = "success"
        except sqlite3.IntegrityError:
            message = "Product name is already exists."
            message_type = "error"
        product = db.execute(
            """
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.cost_price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
            WHERE products.id = ?
            """,
            (id,),
        ).fetchone()
        products = db.execute("""
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.cost_price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
        """).fetchall()
        db.close()
        if request.headers.get("HX-Request"):
            return render_template(
                "products/_edit_product_row.html", product=product
            ) + render_template(
                "products/_edit_message.html",
                message=message,
                message_type=message_type,
            )
        return render_template("products/_product_table.html", products=products)


# =========================================================================================
# =================      AUTO SEARCH ROUTE           ======================================
@product_bp.route("/products/search")
def search_products():
    query = request.args.get("q", "")

    db = get_db()

    products = db.execute(
        """
        SELECT
            products.id,
            products.name,
            categories.name AS category,
            products.price,
            products.cost_price,
            products.stock,
            products.photo
        FROM products
        JOIN categories
        ON products.category_id = categories.id
        WHERE products.name LIKE ?
    """,
        (f"%{query}%",),
    ).fetchall()

    db.close()

    return render_template("products/_product_table.html", products=products)
