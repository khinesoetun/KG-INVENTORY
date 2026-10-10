from flask import Blueprint, render_template
from database import get_db
from io import BytesIO
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/reports")
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


@reports_bp.route("/reports/pdf")
def reports_pdf():
    db = get_db()

    revenue = db.execute("""
        SELECT SUM(sale_items.subtotal) AS revenue
        FROM sale_items
        JOIN sales
            ON sale_items.sale_id = sales.id
        WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
    """).fetchone()
    cost = db.execute("""
    SELECT SUM(sale_items.cost_price * sale_items.quantity) AS cost
    FROM sale_items
    JOIN sales
        ON sale_items.sale_id = sales.id
    WHERE DATE(sales.created_at) >= DATE('now', 'start of month')
""").fetchone()
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
    GROUP BY sale_items.product_id
""").fetchall()
    product_rows = []

    for row in product_performance:
        profit = row["revenue"] - row["cost"]

        product_rows.append(
            {
                "name": row["name"],
                "qty_sold": row["qty_sold"],
                "revenue": row["revenue"],
                "cost": row["cost"],
                "profit": profit,
            }
        )
    cost = cost["cost"] or 0
    revenue = revenue["revenue"] or 0
    gross_profit = revenue - cost
    profit_margin = (gross_profit / revenue * 100) if revenue else 0
    buffer = BytesIO()

    pdf = canvas.Canvas(buffer)
    data = [["Product", "Qty Sold", "Revenue", "Cost", "Profit"]]

    for product in product_rows:
        data.append(
            [
                product["name"],
                product["qty_sold"],
                f"${product['revenue']:.2f}",
                f"${product['cost']:.2f}",
                f"${product['profit']:.2f}",
            ]
        )

    table = Table(data, colWidths=[150, 70, 90, 90, 90])

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), "#0F1629"),
                ("TEXTCOLOR", (0, 0), (-1, 0), "white"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("TEXTCOLOR", (0, 1), (-1, -1), "#334155"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#E2E8F0"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    table.wrapOn(pdf, 500, 300)
    table.drawOn(pdf, 50, 530)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(50, 800, "Inventory Report")

    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 782, "Sales & Profit Summary")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 750, "Total Revenue")
    pdf.drawString(300, 750, "Total Cost")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 732, f"${revenue:.2f}")
    pdf.drawString(300, 732, f"${cost:.2f}")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 700, "Gross Profit")
    pdf.drawString(300, 700, "Profit Margin")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 682, f"${gross_profit:.2f}")
    pdf.drawString(300, 682, f"{profit_margin:.2f}%")

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="inventory_report.pdf",
        mimetype="application/pdf",
    )
