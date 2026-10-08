from flask import Flask
from inventory.dashboard.routes import dashboard_bp
from inventory.products.routes import product_bp
from inventory.categories.routes import category_bp
from inventory.sales.routes import sales_bp
from inventory.reports.routes import reports_bp

app = Flask(__name__)

app.register_blueprint(dashboard_bp)
app.register_blueprint(product_bp)
app.register_blueprint(category_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(reports_bp)

if __name__ == "__main__":
    app.run(debug=True)
