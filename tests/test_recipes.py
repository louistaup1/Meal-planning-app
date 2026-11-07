"""Tests for the recipe rules in recipes.py (no AI involved)."""

from datetime import date

from recipes import build_request, check_against_pantry, describe_pantry, read_filters

TODAY = date(2026, 11, 7)

PANTRY = [
    {"id": 1, "name": "Spaghetti", "category": "Dry pantry", "quantity": 500.0, "unit": "g", "expiry_date": None},
    {"id": 2, "name": "Milk", "category": "Dairy", "quantity": 1.0, "unit": "L", "expiry_date": date(2026, 11, 8)},
    {"id": 3, "name": "Parmesan", "category": "Dairy", "quantity": 50.0, "unit": "g", "expiry_date": date(2026, 12, 1)},
    {"id": 4, "name": "Old cream", "category": "Dairy", "quantity": 1.0, "unit": "cups", "expiry_date": date(2026, 11, 1)},
]


def ingredient(name, amount, unit, pantry_item_id, is_staple=False):
    return {"name": name, "amount": amount, "unit": unit,
            "pantry_item_id": pantry_item_id, "is_staple": is_staple}


# --- read_filters ------------------------------------------------------------

def test_filters_default_to_any():
    assert read_filters({}) == {"cuisine": "Any", "difficulty": "Any", "style": "Any"}


def test_unknown_filter_values_become_any():
    filters = read_filters({"cuisine": "Martian", "difficulty": "Easy", "style": "Comfort"})
    assert filters == {"cuisine": "Any", "difficulty": "Easy", "style": "Comfort"}


# --- describe_pantry and build_request ----------------------------------------

def test_pantry_description_marks_expiring_and_expired_items():
    text = describe_pantry(PANTRY, TODAY)
    assert "id 1: Spaghetti, 500 g (Dry pantry)" in text
    assert "id 2: Milk, 1 L (Dairy), EXPIRES SOON on 2026-11-08" in text
    assert "EXPIRED on 2026-11-01 (don't use)" in text
    assert "Parmesan, 50 g (Dairy)\n" in text  # not expiring soon, so no note


def test_request_includes_only_chosen_filters():
    text = build_request(PANTRY, {"cuisine": "Italian", "difficulty": "Any", "style": "Quick"}, TODAY)
    assert "Cuisine: Italian" in text
    assert "Style: Quick" in text
    assert "Difficulty" not in text


def test_request_without_filters_says_no_preferences():
    text = build_request(PANTRY, read_filters({}), TODAY)
    assert "No preferences" in text


# --- check_against_pantry ----------------------------------------------------

def test_ingredients_are_marked_have_low_assumed_or_missing():
    recipe = {
        "title": "Spaghetti cacio e pepe",
        "ingredients": [
            ingredient("Spaghetti", 200, "g", 1),
            ingredient("Parmesan", 80, "g", 3),       # need 80 g, have 50 g
            ingredient("Black pepper", 1, "tsp", None, is_staple=True),
            ingredient("Pecorino", 50, "g", None),
        ],
    }
    checked = check_against_pantry(recipe, PANTRY)
    statuses = [i["status"] for i in checked["ingredients"]]
    assert statuses == ["have", "low", "assumed", "missing"]
    assert checked["missing"] == ["Pecorino"]


def test_unknown_pantry_id_from_claude_counts_as_missing():
    recipe = {"title": "Soup", "ingredients": [ingredient("Leeks", 2, "pieces", 999)]}
    checked = check_against_pantry(recipe, PANTRY)
    assert checked["ingredients"][0]["status"] == "missing"
    assert checked["ingredients"][0]["pantry_item_id"] is None
    assert checked["missing"] == ["Leeks"]


def test_different_units_are_not_compared():
    # 2 cups vs 1 L can't be compared simply, so we trust Claude that it's enough.
    recipe = {"title": "Pudding", "ingredients": [ingredient("Milk", 2, "cups", 2)]}
    checked = check_against_pantry(recipe, PANTRY)
    assert checked["ingredients"][0]["status"] == "have"


def test_check_does_not_change_the_original_recipe():
    recipe = {"title": "Pasta", "ingredients": [ingredient("Pecorino", 50, "g", None)]}
    check_against_pantry(recipe, PANTRY)
    assert "status" not in recipe["ingredients"][0]
    assert "missing" not in recipe
