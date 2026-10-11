from flask import (
    Blueprint,
    render_template,
    request,
    url_for,
    redirect,
    make_response,
    session,
)
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


# ==========================================================================================
@product_bp.route("/products", methods=["GET", "POST"])
@admin_required
def products():
    message_type = None
    message = None
    product_id = None
    photo_name = None
    page = request.args.get("page", 1, type=int)
    page = max(page, 1)
    db = get_db()

    if request.method == "POST":
        try:
            name = request.form["name"].strip()
            category_id = int(request.form["category_id"])
            price = float(request.form["price"])
            cost_price = float(request.form["cost_price"])
            initial_stock = int(request.form["stock"])

            if not name:
                raise ValueError("Product name is required.")

            if price < 0 or cost_price < 0:
                raise ValueError("Prices cannot be negative.")

            if initial_stock < 0:
                raise ValueError("Initial stock cannot be negative.")

            photo = request.files.get("photo")
            photo_data = process_product_image(photo)

            if photo_data:
                photo_name = f"{uuid.uuid4().hex}.jpg"
                photo_path = os.path.join(UPLOADS_PATH, photo_name)

                with open(photo_path, "wb") as f:
                    f.write(photo_data)

            # Save Product and Initial Stock History together.
            with db:
                cursor = db.execute(
                    """
                    INSERT INTO products (
                        name, category_id, cost_price,
                        price, stock, photo
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        category_id,
                        cost_price,
                        price,
                        initial_stock,
                        photo_name,
                    ),
                )

                product_id = cursor.lastrowid

                if initial_stock > 0:
                    db.execute(
                        """
                        INSERT INTO stock_movements (
                            product_id,
                            movement_type,
                            quantity,
                            reason,
                            user_id
                        )
                        VALUES (?, 'INITIAL', ?, 'Initial Stock', ?)
                        """,
                        (
                            product_id,
                            initial_stock,
                            session.get("user_id"),
                        ),
                    )

            message = "Product added successfully."
            message_type = "success"

        except ValueError as e:
            message = str(e)
            message_type = "error"

        except sqlite3.IntegrityError:
            message = "Product name already exists."
            message_type = "error"

        finally:
            # Remove the newly uploaded photo if saving failed.
            if message_type == "error" and photo_name:
                photo_path = os.path.join(UPLOADS_PATH, photo_name)

                if os.path.isfile(photo_path):
                    os.remove(photo_path)

    product = None

    if product_id is not None and message_type == "success":
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
            (product_id,),
        ).fetchone()
    per_page = 10

    total_count = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

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
    ORDER BY products.id DESC
    LIMIT ? OFFSET ?
    """,
        (per_page, offset),
    ).fetchall()

    categories = db.execute("""
    SELECT id, name
    FROM categories
    ORDER BY name
""").fetchall()

    db.close()

    if request.headers.get("HX-Request"):
        if product:
            response = make_response(
                render_template(
                    "products/add_product_row.html",
                    product=product,
                )
                + render_template(
                    "products/_product_message.html",
                    message=message,
                    message_type=message_type,
                )
            )

            return response

        return render_template(
            "products/_product_message.html",
            message=message,
            message_type=message_type,
        )

    return render_template(
        "products/products.html",
        products=products,
        categories=categories,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        per_page=per_page,
        start_item=offset + 1 if total_count else 0,
        end_item=offset + len(products),
        query="",
    )


# ===================================================================================================
# ==================         DELETE ROUTE        ====================================================
@product_bp.route("/products/<int:id>/delete", methods=["POST"])
@admin_required
def delete_product(id):
    db = get_db()

    product = db.execute("SELECT photo FROM products WHERE id = ?", (id,)).fetchone()
    has_sales = db.execute(
        "SELECT 1 FROM sale_items WHERE product_id = ? LIMIT 1", (id,)
    ).fetchone()

    has_movements = db.execute(
        "SELECT 1 FROM stock_movements WHERE product_id = ? LIMIT 1", (id,)
    ).fetchone()

    message = None

    if product and (has_sales or has_movements):
        if has_sales and has_movements:
            message = "Cannot delete: Sales and Stock Movement records exist."
        elif has_sales:
            message = "Cannot delete: Sales history exists."
        else:
            message = "Cannot delete: Stock Movement history exists."

    elif product:
        photo_name = product["photo"]

        db.execute("DELETE FROM products WHERE id = ?", (id,))
        db.commit()

        # Delete the photo only if no other product uses it
        if photo_name:
            remaining = db.execute(
                "SELECT 1 FROM products WHERE photo = ? LIMIT 1", (photo_name,)
            ).fetchone()

            if not remaining:
                filename = os.path.basename(photo_name)
                photo_path = os.path.realpath(os.path.join(UPLOADS_PATH, filename))
                upload_folder = os.path.realpath(UPLOADS_PATH)

                if (
                    filename == photo_name
                    and os.path.commonpath([upload_folder, photo_path]) == upload_folder
                    and os.path.isfile(photo_path)
                ):
                    os.remove(photo_path)

    else:
        message = "Product not found."

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
    return render_template(
        "products/_product_table.html",
        products=products,
        message=message,
        message_type="error" if message else "success",
    )


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

            photo = request.files.get("photo")
            photo_name = product["photo"]

            if photo and photo.filename:
                photo_data = process_product_image(photo)

                if photo_data:
                    new_photo_name = f"{uuid.uuid4().hex}.jpg"
                    photo_path = os.path.join(UPLOADS_PATH, new_photo_name)

                    with open(photo_path, "wb") as f:
                        f.write(photo_data)

                    photo_name = new_photo_name

            db.execute(
                """
                UPDATE products
                SET name = ?, category_id = ?, cost_price = ?,
                    price = ?, photo = ?
                WHERE id = ?
                """,
                (name, category_id, cost_price, price, photo_name, id),
            )

            db.commit()

            message = "Product updated successfully."
            message_type = "success"

            # Delete the old photo only after a successful update
            old_photo = product["photo"]

            if new_photo_name and old_photo and old_photo != new_photo_name:

                remaining = db.execute(
                    "SELECT 1 FROM products WHERE photo = ? LIMIT 1", (old_photo,)
                ).fetchone()

                if not remaining:
                    filename = os.path.basename(old_photo)
                    old_path = os.path.realpath(os.path.join(UPLOADS_PATH, filename))
                    upload_folder = os.path.realpath(UPLOADS_PATH)

                    if (
                        filename == old_photo
                        and os.path.commonpath([upload_folder, old_path])
                        == upload_folder
                        and os.path.isfile(old_path)
                    ):
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
    page = request.args.get("page", 1, type=int)
    page = max(page, 1)
    per_page = 10
    db = get_db()
    total_count = db.execute(
        """
            SELECT COUNT(*)
            FROM products
            JOIN categories
                ON products.category_id = categories.id
            WHERE products.name LIKE ?
            """,
        (f"%{query}%",),
    ).fetchone()[0]
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page
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
ORDER BY products.id DESC
LIMIT ? OFFSET ?
    """,
        (f"%{query}%", per_page, offset),
    ).fetchall()

    db.close()

    return render_template(
        "products/_product_list.html",
        products=products,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        per_page=per_page,
        start_item=offset + 1 if total_count else 0,
        end_item=offset + len(products),
        query=query,
    )
