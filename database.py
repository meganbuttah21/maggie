import sqlite3
import json
import os

DB_PATH = os.environ.get("DB_PATH", "realty.db")

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                complex_name TEXT NOT NULL,
                room_type   TEXT NOT NULL,
                area        REAL NOT NULL,
                price       REAL NOT NULL,
                source      TEXT NOT NULL,
                description TEXT DEFAULT '',
                photos      TEXT DEFAULT '[]',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_property(self, complex_name, room_type, area, price, source, description, photos):
        cur = self.conn.execute(
            """INSERT INTO properties (complex_name, room_type, area, price, source, description, photos)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (complex_name, room_type, area, price, source, description, json.dumps(photos))
        )
        self.conn.commit()
        return cur.lastrowid

    def _row_to_dict(self, row):
        d = dict(row)
        d["photos"] = json.loads(d["photos"])
        return d

    def search(self, room_type=None, source=None, max_price=None):
        query = "SELECT * FROM properties WHERE 1=1"
        params = []
        if room_type:
            query += " AND room_type = ?"
            params.append(room_type)
        if source:
            query += " AND source = ?"
            params.append(source)
        if max_price:
            query += " AND price <= ?"
            params.append(max_price)
        query += " ORDER BY created_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_all(self):
        rows = self.conn.execute("SELECT * FROM properties ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_by_id(self, prop_id):
        row = self.conn.execute("SELECT * FROM properties WHERE id = ?", (prop_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def delete(self, prop_id):
        self.conn.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
        self.conn.commit()
