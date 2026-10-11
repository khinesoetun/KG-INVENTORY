from flask import Blueprint, render_template, request, url_for, redirect, make_response
from database import get_db, UPLOADS_PATH
from inventory.auth.routes import admin_required
import sqlite3
import os
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename
import uuid

product_bp = Blueprint("product", __name__)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB

def process_product_image(photo):
    if not photo or not photo.filename:
        return None

    filename = secure_filename(photo.filename)

    if "." not in filename:
        raise ValueError("Invalid image filename.")

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Only JPG, PNG, and WebP images are allowed.")

    photo_data = photo.read(MAX_IMAGE_SIZE + 1)

    if len(photo_data) > MAX_IMAGE_SIZE:
        raise ValueError("Image size must not exceed 10 MB.")

    try:
        image = Image.open(BytesIO(photo_data))
        image.verify()

        image = Image.open(BytesIO(photo_data))
        image.load()

    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("The selected file is not a valid image.")

    image.thumbnail((800, 800))

    if image.mode != "RGB":
        image = image.convert("RGB")

    output = BytesIO()
    image.save(output, format="JPEG", quality=85, optimize=True)

    return output.getvalue()
#==========================================================================================
@product_bp.route("/products", methods=["GET", "POST"])
@admin_required
def products():
    message_type = None
    message = None
    product_id = None
    photo_name = None
    error = False
    db = get_db()
    if request.method == "POST":
        try:
            name = request.form["name"]
            category_id = request.form["category_id"]
            price = request.form["price"]
            cost_price = request.form["cost_price"]
            stock = request.form["stock"]
            photo = request.files.get("photo")
            photo_data = process_product_image(photo)

            photo_name = None

            if photo_data:
                photo_name = f"{uuid.uuid4().hex}.jpg"

                with open(os.path.join(UPLOADS_PATH, photo_name), "wb") as f:
                    f.write(photo_data)
            cursor = db.execute(
                """
                     INSERT INTO products(name,category_id,cost_price,price,stock,photo)
                     VALUES (?,?,?,?,?,?)
                    """,
                (name, category_id, cost_price, price, stock, photo_name),
            )
            db.commit()
            product_id = cursor.lastrowid
            message = "Product addede successfully"
            message_type = "success"
        except ValueError as e:
            message = str(e)
            message_type = "error"

        except sqlite3.IntegrityError:
            if photo_name:
                photo_path = os.path.join(UPLOADS_PATH, photo_name)

                if os.path.isfile(photo_path):
                    os.remove(photo_path)

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
@admin_required
def delete_product(id):
    db = get_db()

    product = db.execute(
        "SELECT photo FROM products WHERE id = ?",
        (id,)
    ).fetchone()

    if product:
        photo_name = product["photo"]

        db.execute(
            "DELETE FROM products WHERE id = ?",
            (id,)
        )
        db.commit()

        # Delete the photo only if no other product uses it
        if photo_name:
            remaining = db.execute(
                "SELECT 1 FROM products WHERE photo = ? LIMIT 1",
                (photo_name,)
            ).fetchone()

            if not remaining:
                filename = os.path.basename(photo_name)
                photo_path = os.path.realpath(
                    os.path.join(UPLOADS_PATH, filename)
                )
                upload_folder = os.path.realpath(UPLOADS_PATH)

                if (
                    filename == photo_name
                    and os.path.commonpath(
                        [upload_folder, photo_path]
                    ) == upload_folder
                    and os.path.isfile(photo_path)
                ):
                    os.remove(photo_path)
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
@admin_required
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
        new_photo_name = None

        try:
            name = request.form["name"]
            category_id = request.form["category_id"]
            price = request.form["price"]
            cost_price = request.form["cost_price"]
            stock = request.form["stock"]

            photo = request.files.get("photo")
            photo_name = product["photo"]

            if photo and photo.filename:
                photo_data = process_product_image(photo)

                if photo_data:
                    new_photo_name = f"{uuid.uuid4().hex}.jpg"
                    photo_path = os.path.join(
                        UPLOADS_PATH, new_photo_name
                    )

                    with open(photo_path, "wb") as f:
                        f.write(photo_data)

                    photo_name = new_photo_name

            db.execute(
                """
                UPDATE products
                SET name = ?, category_id = ?, cost_price = ?,
                    price = ?, stock = ?, photo = ?
                WHERE id = ?
                """,
                (
                    name, category_id, cost_price,
                    price, stock, photo_name, id
                ),
            )

            db.commit()

            message = "Product updated successfully."
            message_type = "success"

            # Delete the old photo only after a successful update
            old_photo = product["photo"]

            if new_photo_name and old_photo and old_photo != new_photo_name:
                old_path = os.path.join(UPLOADS_PATH, old_photo)

                if os.path.isfile(old_path):
                    os.remove(old_path)

        except ValueError as e:
            if new_photo_name:
                new_path = os.path.join(UPLOADS_PATH, new_photo_name)
                if os.path.isfile(new_path):
                    os.remove(new_path)

            message = str(e)
            message_type = "error"

        except sqlite3.IntegrityError:
            if new_photo_name:
                new_path = os.path.join(UPLOADS_PATH, new_photo_name)
                if os.path.isfile(new_path):
                    os.remove(new_path)

            message = "Product name already exists."
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
@admin_required
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
