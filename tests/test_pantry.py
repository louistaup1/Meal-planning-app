"""Tests for the pantry rules in pantry.py."""

from datetime import date

from pantry import (
    expiry_status,
    format_quantity,
    group_by_category,
    validate_item,
)


def a_valid_form(**changes):
    form = {
        "name": "Rice",
        "category": "Dry pantry",
        "quantity": "500",
        "unit": "g",
        "expiry_date": "",
    }
    form.update(changes)
    return form


# --- validate_item ---------------------------------------------------------

def test_valid_item_has_no_errors():
    item, errors = validate_item(a_valid_form())
    assert errors == []
    assert item["name"] == "Rice"
    assert item["quantity"] == 500
    assert item["expiry_date"] is None


def test_name_is_required():
    _, errors = validate_item(a_valid_form(name="   "))
    assert "Please enter a name." in errors


def test_unknown_category_is_rejected():
    _, errors = validate_item(a_valid_form(category="Snacks"))
    assert "Please choose a category." in errors


def test_quantity_must_be_a_number():
    _, errors = validate_item(a_valid_form(quantity="lots"))
    assert "Quantity must be a number, like 2 or 0.5." in errors


def test_quantity_cannot_be_negative():
    _, errors = validate_item(a_valid_form(quantity="-1"))
    assert "Quantity can't be negative." in errors


def test_quantity_accepts_comma_as_decimal_point():
    item, errors = validate_item(a_valid_form(quantity="0,5"))
    assert errors == []
    assert item["quantity"] == 0.5


def test_expiry_date_is_read_as_a_date():
    item, errors = validate_item(a_valid_form(expiry_date="2026-12-01"))
    assert errors == []
    assert item["expiry_date"] == date(2026, 12, 1)


# --- expiry_status ---------------------------------------------------------

TODAY = date(2026, 11, 6)


def test_no_expiry_date_has_no_status():
    assert expiry_status(None, TODAY) is None


def test_past_date_is_expired():
    assert expiry_status(date(2026, 11, 5), TODAY) == "expired"


def test_today_and_next_three_days_are_soon():
    assert expiry_status(date(2026, 11, 6), TODAY) == "soon"
    assert expiry_status(date(2026, 11, 9), TODAY) == "soon"


def test_later_dates_are_ok():
    assert expiry_status(date(2026, 11, 10), TODAY) == "ok"


# --- format_quantity and group_by_category ---------------------------------

def test_format_quantity_drops_unneeded_decimals():
    assert format_quantity(2.0) == "2"
    assert format_quantity(0.5) == "0.5"


def test_group_by_category_follows_category_order_and_sorts_names():
    items = [
        {"name": "milk", "category": "Dairy"},
        {"name": "Rice", "category": "Dry pantry"},
        {"name": "Butter", "category": "Dairy"},
    ]
    groups = group_by_category(items)
    assert [category for category, _ in groups] == ["Dry pantry", "Dairy"]
    assert [item["name"] for item in groups[1][1]] == ["Butter", "milk"]
