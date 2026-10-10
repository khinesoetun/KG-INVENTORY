import sqlite3

db = sqlite3.connect("inventory.db")

tables = db.execute("""
    SELECT sql
    FROM sqlite_master
    WHERE type = 'table'
    AND sql IS NOT NULL
    ORDER BY name
""").fetchall()

for table in tables:
    print(table[0])
    print()

db.close()