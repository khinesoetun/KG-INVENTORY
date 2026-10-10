from flask import Flask
from inventory.dashboard.routes import dashboard_bp
from inventory.products.routes import product_bp
from inventory.categories.routes import category_bp
from inventory.sales.routes import sales_bp
from inventory.reports.routes import reports_bp
from inventory.auth.routes import auth_bp, create_initial_admin
from flask import  send_from_directory
from database import UPLOADS_PATH
import webbrowser
from dotenv import load_dotenv
import os


load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ["KG_INVENTORY_SECRET_KEY"]

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    print("UPLOAD PATH:", UPLOADS_PATH)
    print("FILE:", filename)
    return send_from_directory(UPLOADS_PATH, filename)

app.register_blueprint(dashboard_bp)
app.register_blueprint(product_bp)
app.register_blueprint(category_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(auth_bp)
create_initial_admin()


if __name__ == "__main__":
    #webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)
