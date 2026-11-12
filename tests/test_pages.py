"""Tests that click through the pantry pages, like a person would."""

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", password="test-password")
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    return client


def test_empty_pantry_shows_a_hint(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Your pantry is empty" in page.data


def test_add_edit_and_remove_an_item(client):
    # Add
    client.post("/items/new", data={
        "name": "Spaghetti", "category": "Dry pantry",
        "quantity": "500", "unit": "g", "expiry_date": "",
    })
    page = client.get("/")
    assert b"Spaghetti" in page.data
    assert b"500 g" in page.data

    # Edit (the first item gets id 1)
    client.post("/items/1/edit", data={
        "name": "Spaghetti", "category": "Dry pantry",
        "quantity": "250", "unit": "g", "expiry_date": "",
    })
    assert b"250 g" in client.get("/").data

    # Remove
    page = client.post("/items/1/delete", follow_redirects=True)
    assert b"Removed Spaghetti." in page.data
    assert b'<span class="item-name">Spaghetti' not in page.data


def test_invalid_form_shows_errors_and_saves_nothing(client):
    page = client.post("/items/new", data={
        "name": "", "category": "Dairy", "quantity": "abc", "unit": "", "expiry_date": "",
    })
    assert b"Please enter a name." in page.data
    assert b"Your pantry is empty" in client.get("/").data


def test_categories_fold_and_show_counts(client):
    client.post("/items/new", data={"name": "Rice", "category": "Dry pantry",
                                    "quantity": "1", "unit": "kg", "expiry_date": ""})
    client.post("/items/new", data={"name": "Pasta", "category": "Dry pantry",
                                    "quantity": "500", "unit": "g", "expiry_date": ""})
    page = client.get("/").data
    assert b'<details class="category category-dry-pantry" data-category="Dry pantry" open>' in page
    assert b"2 items" in page
