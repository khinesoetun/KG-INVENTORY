from flask import Blueprint, render_template, request, url_for, make_response
from database import get_db
import json
from inventory.auth.routes import login_required

sales_bp = Blueprint("sales", __name__)


@sales_bp.route("/sales")
@login_required
def sales():

    db = get_db()
    products = db.execute("""
    SELECT
    products.id,
    products.name,
    categories.name AS category,
    products.price,
    products.stock,
    products.photo
    FROM products
    JOIN categories
    ON products.category_id = categories.id
    """).fetchall()
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
    sales = db.execute("""
            SELECT
            sales.id,
            sales.total,
            sales.created_at,
            COUNT(sale_items.id) AS item_count
        FROM sales
        LEFT JOIN sale_items
        ON sales.id = sale_items.sale_id
        GROUP BY sales.id
        ORDER BY sales.id DESC
        LIMIT 5
    """).fetchall()
    db.close()
    return render_template(
        "sales/sales.html", products=products, categories=categories, sales=sales
    )


# ======================================================================
# ================ SEARCH PRODUCTS       ==============================
@sales_bp.route("/sales/search")
@login_required
def search_products():
    query = request.args.get("q", "")
    category = request.args.get("categories", "")

    db = get_db()

    if query and category:
        products = db.execute(
            """
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
            WHERE products.name LIKE ?
            AND products.category_id = ?
            """,
            (f"%{query}%", category),
        ).fetchall()

    elif query:
        products = db.execute(
            """
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
            WHERE products.name LIKE ?
            """,
            (f"%{query}%",),
        ).fetchall()

    elif category:
        products = db.execute(
            """
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
            WHERE products.category_id = ?
            """,
            (category,),
        ).fetchall()

    else:
        products = db.execute("""
            SELECT
                products.id,
                products.name,
                categories.name AS category,
                products.price,
                products.stock,
                products.photo
            FROM products
            JOIN categories
            ON products.category_id = categories.id
            """).fetchall()

    db.close()

    return render_template("sales/_product_table.html", products=products)


# ====================================================================================
# =================      SALE ROUTE      =============================================
@sales_bp.route("/sales/complete", methods=["POST"])
@login_required
def complete_sale():
    cart = request.form.get("cart")
    cart = json.loads(cart)
    db = get_db()
    total = 0

    for item in cart:

        product = db.execute(
            "SELECT id, price FROM products WHERE id = ?", (item["id"],)
        ).fetchone()

        quantity = item["quantity"]
        price = product["price"]
        total += price * quantity

    received = float(request.form.get("received", 0))
    print("TOTAL:", total)
    print("RECEIVED:", received)

    change = received - total
    if received < total:
        return "Insufficient received amount", 400
    change = received - total
    sale = db.execute(
        """
      INSERT INTO sales(total,received,change)
      VALUES(?,?,?)

    """,
        (total, received, change),
    )
    for item in cart:
        product = db.execute(
            "SELECT id , price,cost_price FROM products WHERE id = ?", (item["id"],)
        ).fetchone()

        quantity = item["quantity"]
        price = product["price"]
        cost_price = product["cost_price"]
        subtotal = price * quantity
        # reduce product
        db.execute(
            "UPDATE products SET stock = stock - ? WHERE id = ?",
            (item["quantity"], item["id"]),
        )
        db.execute(
            """
         INSERT INTO sale_items
         (sale_id,product_id,quantity,price,cost_price,subtotal)
         VALUES (?,?,?,?,?,?)
        """,
            (sale.lastrowid, product["id"], quantity, price, cost_price, subtotal),
        )

    db.commit()
    products = db.execute("""
                SELECT
                    products.id,
                    products.name,
                    categories.name AS category,
                    products.price,
                    products.stock,
                    products.photo
                FROM products
                JOIN categories
                ON products.category_id = categories.id
                """).fetchall()
    db.close()
    response = make_response("Sale completed")
    response.headers["HX-Refresh"] = "true"
    return response


# ========================================================================================
# =====================  ALL SALES ROUTE     =============================================
@sales_bp.route("/sales/all")
@login_required
def all_sales():
    db = get_db()
    sale_id = request.args.get("sale_id", "")
    date = request.args.get("date", "")
    print(date)
    if sale_id and date:
        sales = db.execute(
            """
        SELECT
            sales.id,
            sales.total,
            sales.received,
            sales.change,
            sales.created_at,
            COUNT(sale_items.id) AS item_count
        FROM sales
        LEFT JOIN sale_items
        ON sales.id = sale_items.sale_id
        WHERE sales.id = ? AND DATE(sales.created_at)=?
        GROUP BY sales.id
        ORDER BY sales.id DESC
    """,
            (sale_id, date),
        ).fetchall()
    elif sale_id:
        sales = db.execute(
            """
        SELECT
            sales.id,
            sales.total,
            sales.received,
            sales.change,
            sales.created_at,
            COUNT(sale_items.id) AS item_count
        FROM sales
        LEFT JOIN sale_items
        ON sales.id = sale_items.sale_id
        WHERE sales.id = ?
        GROUP BY sales.id
        ORDER BY sales.id DESC
    """,
            (sale_id,),
        ).fetchall()
    elif date:
        sales = db.execute(
            """
            SELECT
                sales.id,
                sales.total,
                sales.received,
                sales.change,
                sales.created_at,
                COUNT(sale_items.id) AS item_count
            FROM sales
            LEFT JOIN sale_items
            ON sales.id = sale_items.sale_id
            WHERE DATE(sales.created_at) = ?
            GROUP BY sales.id
            ORDER BY sales.id DESC
        """,
            (date,),
        ).fetchall()
    else:
        sales = db.execute("""
                SELECT
                sales.id,
                sales.total,
                sales.received,
                sales.change,
                sales.created_at,
                COUNT(sale_items.id) AS item_count
            FROM sales
            LEFT JOIN sale_items
            ON sales.id = sale_items.sale_id
            GROUP BY sales.id
            ORDER BY sales.id DESC
                """).fetchall()
    return render_template("sales/all_sales.html", sales=sales)


# =================================================================================
# ===============        SALE DETAIL ROUTE       =================================
@sales_bp.route("/sales/<int:sale_id>")
@login_required
def sale_detail(sale_id):
    db = get_db()

    sale = db.execute(
        """
        SELECT id, total, received, change, created_at
        FROM sales
        WHERE id = ?
    """,
        (sale_id,),
    ).fetchone()
    items = db.execute(
        """
        SELECT
            products.name,
            sale_items.quantity,
            sale_items.price,
            sale_items.subtotal
        FROM sale_items
        JOIN products
        ON sale_items.product_id = products.id
        WHERE sale_items.sale_id = ?
    """,
        (sale_id,),
    ).fetchall()
    db.close()

    return render_template("sales/_sale_detail.html", sale=sale, items=items)
