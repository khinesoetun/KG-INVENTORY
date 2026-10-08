from flask import Blueprint, render_template
from database import get_db

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def home():
    db = get_db()
    total_categories = db.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    total_sales = db.execute("SELECT SUM(total) FROM sales").fetchone()[0] or 0
    total_stock = db.execute("SELECT SUM(stock) FROM products").fetchone()[0]
    low_stock = db.execute(
        "SELECT COUNT (*) FROM products WHERE stock <= 5"
    ).fetchone()[0]
    sales_overview = db.execute("""
    SELECT
        DATE(created_at) AS sale_date,
        SUM(total) AS revenue
    FROM sales
    GROUP BY DATE(created_at)
    ORDER BY sale_date DESC
    LIMIT 7
""").fetchall()
    recent_sales = db.execute("""
    SELECT id, total, created_at
    FROM sales
    ORDER BY created_at DESC
    LIMIT 5
""").fetchall()
    low_stock_products = db.execute("""
    SELECT name, stock
    FROM products
    WHERE stock <= 5
    ORDER BY stock ASC
    LIMIT 5
""").fetchall()
    db.close()
    sales_overview = list(reversed(sales_overview))

    chart_labels = []
    chart_revenue = []

    for row in sales_overview:
        chart_labels.append(row["sale_date"][5:])
        chart_revenue.append(row["revenue"])

    return render_template(
        "dashboard/home.html",
        total_categories=total_categories,
        total_stock=total_stock,
        low_stock=low_stock,
        total_sales=total_sales,
        chart_labels=chart_labels,
        chart_revenue=chart_revenue,
        recent_sales=recent_sales,
        low_stock_products=low_stock_products,
    )
