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

def test_filters_default_to_main_dish_for_dinner_and_two_people():
    assert read_filters({}) == {"meal": "Dinner", "dish_type": "Main", "cuisine": "Any",
                                "difficulty": "Any", "style": "Any", "people": 2}


def test_unknown_filter_values_fall_back_to_defaults():
    filters = read_filters({"meal": "Brunch", "dish_type": "Snack", "cuisine": "Martian",
                            "difficulty": "Easy", "style": "Comfort", "people": "4"})
    assert filters == {"meal": "Dinner", "dish_type": "Main", "cuisine": "Any",
                       "difficulty": "Easy", "style": "Comfort", "people": 4}


def test_request_names_the_meal_and_dish_type():
    text = build_request(PANTRY, read_filters({"meal": "Lunch", "dish_type": "Dessert", "people": "4"}), TODAY)
    assert "Suggest up to 3 dessert recipes for lunch, for 4 people." in text
    text = build_request(PANTRY, read_filters({}), TODAY)
    assert "Suggest up to 3 main dish recipes for dinner, for 2 people." in text
    text = build_request(PANTRY, read_filters({"meal": "Breakfast", "dish_type": "Any"}), TODAY)
    assert "recipes (any kind of dish) for breakfast" in text


def test_bad_people_values_fall_back_to_two():
    assert read_filters({"people": "lots"})["people"] == 2
    assert read_filters({"people": "50"})["people"] == 2


def test_request_says_how_many_people():
    assert "for 1 person" in build_request(PANTRY, read_filters({"people": "1"}), TODAY)
    assert "for 4 people" in build_request(PANTRY, read_filters({"people": "4"}), TODAY)


# --- describe_pantry and build_request ----------------------------------------

def test_pantry_description_marks_expiring_and_expired_items():
    text = describe_pantry(PANTRY, TODAY)
    assert "id 1: Spaghetti, 500 g (Dry pantry)" in text
    assert "id 2: Milk, 1 L (Dairy), EXPIRES SOON on 2026-11-08" in text
    assert "EXPIRED on 2026-11-01 (don't use)" in text
    assert "Parmesan, 50 g (Dairy)\n" in text  # not expiring soon, so no note


def test_request_includes_only_chosen_filters():
    text = build_request(PANTRY, read_filters({"cuisine": "Italian", "style": "Quick"}), TODAY)
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
