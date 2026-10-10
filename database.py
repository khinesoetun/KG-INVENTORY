import os
import sqlite3


if os.name == "nt":
    APP_DATA = os.path.join(
        os.environ["LOCALAPPDATA"],
        "KG Inventory"
    )
else:
    APP_DATA = os.path.join(
        os.path.expanduser("~"),
        ".local",
        "share",
        "KG Inventory"
    )
UPLOADS_PATH = os.path.join(APP_DATA, "uploads")

DB_PATH = os.path.join(APP_DATA, "inventory.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(UPLOADS_PATH, exist_ok=True)
os.makedirs(
    os.path.join(UPLOADS_PATH, "categories-photo"),
    exist_ok=True
)


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()

    with open(SCHEMA_PATH, "r", encoding="utf-8") as file:
        schema = file.read()

    db.executescript(schema)
    db.commit()
    db.close()


init_db()