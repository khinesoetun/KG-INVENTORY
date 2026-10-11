from flask import Blueprint, render_template, request, session
from database import get_db
from inventory.auth.routes import admin_required
import sqlite3

stock_movements_bp = Blueprint(
    "stock_movements",
    __name__,
)


@stock_movements_bp.route(
    "/stock-movements",
    methods=["GET", "POST"],
)
@admin_required
def stock_movements():
    db = get_db()
    message = None
    message_type = None

    if request.method == "POST":
        try:
            product_id = int(request.form.get("product_id", ""))
            movement_type = request.form.get("movement_type", "")
            quantity = int(request.form.get("quantity", ""))

            if movement_type not in ("IN", "OUT"):
                raise ValueError("Select Stock IN or Stock OUT.")

            if quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")

            product = db.execute(
                "SELECT id, stock FROM products WHERE id = ?",
                (product_id,),
            ).fetchone()

            if product is None:
                raise ValueError("Selected product was not found.")

            if movement_type == "OUT" and quantity > product["stock"]:
                raise ValueError("Stock OUT exceeds current stock.")

            reason = request.form.get("reason", "").strip()

            with db:
                if movement_type == "IN":
                    db.execute(
                        """
                        UPDATE products
                        SET stock = stock + ?
                        WHERE id = ?
                        """,
                        (quantity, product_id),
                    )
                else:
                    cursor = db.execute(
                        """
                        UPDATE products
                        SET stock = stock - ?
                        WHERE id = ?
                        AND stock >= ?
                        """,
                        (quantity, product_id, quantity),
                    )

                    if cursor.rowcount != 1:
                        raise ValueError(
                            "Insufficient stock. Please refresh and try again."
                        )

                db.execute(
                    """
                    INSERT INTO stock_movements (
                        product_id,
                        movement_type,
                        quantity,
                        reason,
                        user_id
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        movement_type,
                        quantity,
                        reason or None,
                        session.get("user_id"),
                    ),
                )

            message = f"Stock {movement_type} recorded successfully."
            message_type = "success"

        except ValueError as error:
            message = str(error)
            message_type = "error"

        except sqlite3.Error:
            db.rollback()
            message = "Database error. No stock movement was saved."
            message_type = "error"

    products = db.execute("""
        SELECT id, name, stock
        FROM products
        ORDER BY name
    """).fetchall()

    movements = db.execute("""
        SELECT
            stock_movements.*,
            products.name AS product_name,
            users.username AS username
        FROM stock_movements
        JOIN products
            ON stock_movements.product_id = products.id
        LEFT JOIN users
            ON stock_movements.user_id = users.id
        ORDER BY stock_movements.created_at DESC,
                 stock_movements.id DESC
    """).fetchall()

    db.close()

    return render_template(
        "stock_movements/stock_movements.html",
        products=products,
        movements=movements,
        message=message,
        message_type=message_type,
    )


# =============================================================================
@stock_movements_bp.route("/stock-movements/search")
@admin_required
def search_products():
    query = request.args.get("q", "").strip()

    db = get_db()

    products = db.execute(
        """
        SELECT id, name, stock
        FROM products
        WHERE name LIKE ?
        ORDER BY name
        LIMIT 20
        """,
        (f"%{query}%",),
    ).fetchall()

    db.close()

    return render_template(
        "stock_movements/_product_results.html",
        products=products,
    )


# ========================================================================================
@stock_movements_bp.route("/stock-movements/filter")
@admin_required
def filter_movements():
    query = request.args.get("q", "").strip()
    movement_type = request.args.get("movement_type", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    db = get_db()

    sql = """
        SELECT
            stock_movements.*,
            products.name AS product_name,
            users.username AS username
        FROM stock_movements
        JOIN products
            ON stock_movements.product_id = products.id
        LEFT JOIN users
            ON stock_movements.user_id = users.id
        WHERE products.name LIKE ?
    """

    params = [f"%{query}%"]

    if movement_type in ("IN", "OUT", "INITIAL"):
        sql += " AND stock_movements.movement_type = ?"
        params.append(movement_type)

    if start_date:
        sql += " AND date(stock_movements.created_at) >= date(?)"
        params.append(start_date)

    if end_date:
        sql += " AND date(stock_movements.created_at) <= date(?)"
        params.append(end_date)

    sql += """
        ORDER BY stock_movements.created_at DESC,
                 stock_movements.id DESC
    """

    movements = db.execute(sql, params).fetchall()
    db.close()

    return render_template(
        "stock_movements/_movement_rows.html",
        movements=movements,
    )
