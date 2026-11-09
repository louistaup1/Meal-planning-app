"""
Saving and loading pantry items.

Everything is stored in a single SQLite file (for example "pantry.db").
Each function opens the file, does one job, and closes it again.
"""

import json
import sqlite3
from datetime import date, datetime


def connect(db_path):
    """Open the database file. Rows can then be read like dictionaries."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path):
    """Create the pantry table if it doesn't exist yet."""
    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pantry_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,
                quantity    REAL NOT NULL,
                unit        TEXT NOT NULL DEFAULT '',
                expiry_date TEXT
            )
            """
        )
        # Recipes you've pasted in yourself. Kept exactly as you typed them.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS my_recipes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                text        TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        # Each suggested recipe is saved here, so you can open it again later.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS suggestions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                recipe_json TEXT NOT NULL
            )
            """
        )


def _row_to_item(row):
    """Turn a database row into a plain dictionary, with a real date object."""
    item = dict(row)
    if item["expiry_date"]:
        item["expiry_date"] = date.fromisoformat(item["expiry_date"])
    return item


def _date_to_text(value):
    """Dates are stored as text like '2026-11-06'."""
    if value is None:
        return None
    return value.isoformat()


def get_all_items(db_path):
    with connect(db_path) as connection:
        rows = connection.execute("SELECT * FROM pantry_items").fetchall()
    return [_row_to_item(row) for row in rows]


def get_item(db_path, item_id):
    """Return one item, or None if there is no item with that id."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM pantry_items WHERE id = ?", (item_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def add_item(db_path, item):
    """Save a new item and return its id."""
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO pantry_items (name, category, quantity, unit, expiry_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item["name"], item["category"], item["quantity"], item["unit"],
             _date_to_text(item["expiry_date"])),
        )
        return cursor.lastrowid


def update_item(db_path, item_id, item):
    with connect(db_path) as connection:
        connection.execute(
            """
            UPDATE pantry_items
            SET name = ?, category = ?, quantity = ?, unit = ?, expiry_date = ?
            WHERE id = ?
            """,
            (item["name"], item["category"], item["quantity"], item["unit"],
             _date_to_text(item["expiry_date"]), item_id),
        )


def delete_item(db_path, item_id):
    with connect(db_path) as connection:
        connection.execute("DELETE FROM pantry_items WHERE id = ?", (item_id,))


def save_suggestion(db_path, recipe):
    """Save one suggested recipe (a dictionary) and return its id."""
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO suggestions (created_at, recipe_json) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), json.dumps(recipe)),
        )
        return cursor.lastrowid


def get_suggestion(db_path, suggestion_id):
    """Return a saved recipe as a dictionary, or None if it doesn't exist."""
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT recipe_json FROM suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["recipe_json"])


# --- My recipes ---------------------------------------------------------------

def add_my_recipe(db_path, title, text):
    """Save a recipe you pasted in and return its id."""
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO my_recipes (title, text, created_at) VALUES (?, ?, ?)",
            (title, text, datetime.now().isoformat(timespec="seconds")),
        )
        return cursor.lastrowid


def get_all_my_recipes(db_path):
    """All your saved recipes, sorted by title."""
    with connect(db_path) as connection:
        rows = connection.execute(
            "SELECT * FROM my_recipes ORDER BY title COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def get_my_recipe(db_path, recipe_id):
    with connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM my_recipes WHERE id = ?", (recipe_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_my_recipe(db_path, recipe_id):
    with connect(db_path) as connection:
        connection.execute("DELETE FROM my_recipes WHERE id = ?", (recipe_id,))
