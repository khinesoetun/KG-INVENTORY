from flask import Blueprint, render_template
from database import get_db
from io import BytesIO
from flask import send_file
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

    buffer = BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35,
    )
    pdfmetrics.registerFont(
        TTFont(
            "NotoSansMyanmar",
            "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
        )
    )

    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Inventory Report", styles["Title"]),
        Paragraph("Sales &amp; Profit Summary", styles["Normal"]),
        Spacer(1, 20),
    ]

    summary_data = [
        ["Total Revenue", "Total Cost", "Gross Profit", "Profit Margin"],
        [
            f"${revenue:.2f}",
            f"${cost:.2f}",
            f"${gross_profit:.2f}",
            f"{profit_margin:.2f}%",
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[180, 180, 180, 180],
    )

    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F1629")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    elements.extend(
        [
            summary_table,
            Spacer(1, 30),
            Paragraph("Product Performance", styles["Heading2"]),
            Spacer(1, 10),
        ]
    )

    data = [["Product", "Qty Sold", "Revenue", "Cost", "Profit"]]

    for product in product_performance:
        product_revenue = product["revenue"] or 0
        product_cost = product["cost"] or 0
        product_profit = product_revenue - product_cost

        data.append(
            [
                product["name"],
                str(product["qty_sold"] or 0),
                f"${product_revenue:.2f}",
                f"${product_cost:.2f}",
                f"${product_profit:.2f}",
            ]
        )

    table = Table(
        data,
        colWidths=[300, 100, 120, 120, 120],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F1629")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#334155")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    elements.append(table)

    pdf.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="inventory_report.pdf",
        mimetype="application/pdf",
    )
