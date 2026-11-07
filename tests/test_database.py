"""Tests for saving and loading items in database.py."""

from datetime import date

import database


def make_item(**changes):
    item = {
        "name": "Milk",
        "category": "Dairy",
        "quantity": 1.0,
        "unit": "L",
        "expiry_date": date(2026, 11, 7),
    }
    item.update(changes)
    return item


def test_add_then_read_back(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(db_path)

    item_id = database.add_item(db_path, make_item())
    saved = database.get_item(db_path, item_id)

    assert saved["name"] == "Milk"
    assert saved["quantity"] == 1.0
    assert saved["expiry_date"] == date(2026, 11, 7)


def test_update_changes_the_item(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(db_path)
    item_id = database.add_item(db_path, make_item())

    database.update_item(db_path, item_id, make_item(quantity=0.5, expiry_date=None))

    saved = database.get_item(db_path, item_id)
    assert saved["quantity"] == 0.5
    assert saved["expiry_date"] is None


def test_delete_removes_the_item(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(db_path)
    item_id = database.add_item(db_path, make_item())

    database.delete_item(db_path, item_id)

    assert database.get_item(db_path, item_id) is None
    assert database.get_all_items(db_path) == []


def test_save_and_read_back_a_suggestion(tmp_path):
    db_path = tmp_path / "test.db"
    database.init_db(db_path)
    recipe = {"title": "Pasta", "ingredients": [{"name": "Spaghetti", "amount": 200}], "steps": ["Boil"]}

    suggestion_id = database.save_suggestion(db_path, recipe)

    assert database.get_suggestion(db_path, suggestion_id) == recipe
    assert database.get_suggestion(db_path, 999) is None
