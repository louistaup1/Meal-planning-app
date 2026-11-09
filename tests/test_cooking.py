"""Tests for the cooking rules in cooking.py."""

from cooking import apply_cooking, cook_checklist
from recipes import check_against_pantry

PANTRY = [
    {"id": 1, "name": "Spaghetti", "category": "Dry pantry", "quantity": 500.0, "unit": "g", "expiry_date": None},
    {"id": 2, "name": "Garlic", "category": "Vegetables", "quantity": 3.0, "unit": "pieces", "expiry_date": None},
    {"id": 3, "name": "Milk", "category": "Dairy", "quantity": 1.0, "unit": "L", "expiry_date": None},
]


def ingredient(name, amount, unit, pantry_item_id, is_staple=False):
    return {"name": name, "amount": amount, "unit": unit,
            "pantry_item_id": pantry_item_id, "is_staple": is_staple}


RECIPE = check_against_pantry({
    "title": "Garlic spaghetti",
    "ingredients": [
        ingredient("Spaghetti", 200, "g", 1),           # 0: in pantry, same unit
        ingredient("Garlic", 2, "pieces", 2),           # 1: in pantry
        ingredient("Milk", 1, "cups", 3),               # 2: in pantry, different unit
        ingredient("Salt", 1, "tsp", None, True),       # 3: staple, not asked about
        ingredient("Fresh parsley", 1, "bunches", None),  # 4: missing
        ingredient("Garlic", 1, "pieces", 2),           # 5: same pantry item again
    ],
}, PANTRY)


def ticked(*indexes, **amounts):
    """Build form answers: ticked boxes plus used amounts like used_0="200"."""
    form = {f"have_{i}": "on" for i in indexes}
    form.update(amounts)
    return form


# --- cook_checklist -----------------------------------------------------------

def test_checklist_skips_staples_and_prefills_amounts():
    rows = cook_checklist(RECIPE, PANTRY)
    assert [r["index"] for r in rows] == [0, 1, 2, 4, 5]
    assert rows[0]["have"] is True and rows[0]["used"] == "200"
    assert rows[0]["pantry_quantity"] == "500" and rows[0]["pantry_unit"] == "g"


def test_checklist_leaves_amount_blank_when_units_differ():
    milk = cook_checklist(RECIPE, PANTRY)[2]
    assert milk["used"] == ""
    assert milk["recipe_unit"] == "cups"


def test_missing_ingredients_start_unticked():
    parsley = cook_checklist(RECIPE, PANTRY)[3]
    assert parsley["in_pantry"] is False
    assert parsley["have"] is False


# --- apply_cooking ------------------------------------------------------------

def test_used_amounts_are_taken_off_the_pantry():
    form = ticked(0, 1, 2, 5, used_0="200", used_1="2", used_2="0.25", used_5="1")
    changes, to_buy, errors = apply_cooking(RECIPE, PANTRY, form)
    assert errors == []
    assert changes == {1: 300.0, 2: None, 3: 0.75}  # garlic: 3 - 2 - 1 = 0, so removed
    assert to_buy == ["1 bunches Fresh parsley"]


def test_a_blank_amount_changes_nothing():
    form = ticked(0, 1, 2, 5, used_0="", used_1="", used_2="", used_5="")
    changes, _, _ = apply_cooking(RECIPE, PANTRY, form)
    assert changes == {}


def test_using_more_than_you_have_removes_the_item():
    form = ticked(0, used_0="900")
    changes, _, _ = apply_cooking(RECIPE, PANTRY, form)
    assert changes[1] is None


def test_unticked_pantry_items_go_on_the_shopping_list():
    form = ticked(1, 2, 4, 5, used_1="2", used_2="", used_5="1")  # spaghetti unticked, parsley ticked
    changes, to_buy, _ = apply_cooking(RECIPE, PANTRY, form)
    assert to_buy == ["200 g Spaghetti"]
    assert 1 not in changes


def test_amounts_that_are_not_numbers_stop_any_changes():
    form = ticked(0, 1, used_0="lots", used_1="-1")
    changes, _, errors = apply_cooking(RECIPE, PANTRY, form)
    assert changes == {}
    assert errors == ["Please check the amount used for Spaghetti.",
                      "Please check the amount used for Garlic."]


def test_comma_decimals_are_accepted():
    form = ticked(2, used_2="0,5")
    changes, _, errors = apply_cooking(RECIPE, PANTRY, form)
    assert errors == []
    assert changes == {3: 0.5}
