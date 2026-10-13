from flask import Blueprint, render_template, request, send_file
from database import get_db
import weasyprint_helper
from weasyprint import HTML
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from inventory.auth.routes import admin_required

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports")
@admin_required
def reports():
    db = get_db()
    revenue = db.execute(
        "SELECT SUM(sale_items.subtotal) AS revenue FROM sale_items JOIN sales ON sale_items.sale_id = sales.id WHERE DATE(sales.created_at) >= DATE('now', 'start of month')"
    ).fetchone()
    revenue = revenue["revenue"] or 0
    cost = db.execute("""SELECT SUM(sale_items.cost_price * sale_items.quantity) AS cost
    FROM sale_items
    JOIN sales
        ON sale_items.sale_id = sales.id
    WHERE DATE(sales.created_at) >= DATE('now', 'start of month')""").fetchone()
    cost = cost["cost"] or 0
    gross_profit = revenue - cost
    profit_margin = (gross_profit / revenue * 100) if revenue else 0
    product_performance = db.execute("""
    SELECT
    products.name,
    sale_items.product_id,
    SUM(sale_items.quantity) AS qty_sold,
    SUM(sale_items.subtotal) AS revenue,
    SUM(sale_items.cost_price * sale_items.quantity) AS cost
FROM sale_items
JOIN products
    ON sale_items.product_id = products.id
JOIN sales
    ON sale_items.sale_id = sales.id
WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
GROUP BY sale_items.product_id;
    """).fetchall()
    product_rows = []
    for row in product_performance:
        product_revenue = row["revenue"]
        product_cost = row["cost"]
        profit = product_revenue - product_cost
        product_rows.append(
            {
                "name": row["name"],
                "qty_sold": row["qty_sold"],
                "revenue": product_revenue,
                "cost": product_cost,
                "profit": profit,
            }
        )
    print(product_rows)

    sales_overview = db.execute("""
    SELECT
        DATE(created_at) AS sale_date,
        SUM(total) AS revenue
    FROM sales
    GROUP BY DATE(created_at)
    ORDER BY sale_date
""").fetchall()
    profit_overview = db.execute("""
    SELECT
        DATE(sales.created_at) AS sale_date,
        SUM(
            sale_items.subtotal -
            (sale_items.cost_price * sale_items.quantity)
        ) AS profit
    FROM sales
    JOIN sale_items
        ON sales.id = sale_items.sale_id
    GROUP BY DATE(sales.created_at)
    ORDER BY sale_date
""").fetchall()
    db.close()
    chart_labels = []
    chart_revenue = []

    for row in sales_overview:
        chart_labels.append(row["sale_date"][5:])
        chart_revenue.append(row["revenue"])
    chart_profit = []

    for row in profit_overview:
        chart_profit.append(row["profit"])
    return render_template(
        "reports/reports.html",
        revenue=revenue,
        cost=cost,
        gross_profit=gross_profit,
        profit_margin=profit_margin,
        product_rows=product_rows,
        chart_labels=chart_labels,
        chart_revenue=chart_revenue,
        chart_profit=chart_profit,
    )


# ================================================================================================
@reports_bp.route("/reports/pdf")
@admin_required
def reports_pdf():
    db = get_db()

    revenue_row = db.execute("""
        SELECT SUM(sale_items.subtotal) AS revenue
        FROM sale_items
        JOIN sales
            ON sale_items.sale_id = sales.id
        WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
    """).fetchone()

    cost_row = db.execute("""
        SELECT SUM(sale_items.cost_price * sale_items.quantity) AS cost
        FROM sale_items
        JOIN sales
            ON sale_items.sale_id = sales.id
        WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
    """).fetchone()

    product_performance = db.execute("""
        SELECT
            products.name,
            SUM(sale_items.quantity) AS qty_sold,
            SUM(sale_items.subtotal) AS revenue,
            SUM(sale_items.cost_price * sale_items.quantity) AS cost
        FROM sale_items
        JOIN products
            ON sale_items.product_id = products.id
        JOIN sales
            ON sale_items.sale_id = sales.id
        WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
        GROUP BY sale_items.product_id
        ORDER BY revenue DESC
    """).fetchall()

    revenue = revenue_row["revenue"] or 0
    cost = cost_row["cost"] or 0
    gross_profit = revenue - cost
    profit_margin = (gross_profit / revenue * 100) if revenue else 0

    html = render_template(
        "reports/monthly_report.html",
        revenue=revenue,
        cost=cost,
        gross_profit=gross_profit,
        profit_margin=profit_margin,
        product_performance=product_performance,
    )

    pdf_bytes = HTML(
        string=html,
        base_url=request.root_url,
    ).write_pdf()

    return send_file(
        BytesIO(pdf_bytes),
        as_attachment=True,
        download_name="inventory_report.pdf",
        mimetype="application/pdf",
    )
