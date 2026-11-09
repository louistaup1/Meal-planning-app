"""
Cooking rules (no web pages, no AI in here).

When you cook a recipe, this file:
  1. builds the "What did you use?" checklist, and
  2. turns your answers into pantry changes and a "to buy" list.
"""

from pantry import format_quantity, same_unit


def cook_checklist(checked_recipe, pantry_items):
    """
    One row per ingredient that's worth asking about.

    `checked_recipe` comes from recipes.check_against_pantry(). Basic staples
    (salt, pepper, oil) are left out. Each row is a dictionary with:
      index        - the ingredient's position in the recipe (used in form field names)
      name, recipe_amount, recipe_unit
      in_pantry    - True if it matches something in your pantry
      have         - whether the box starts ticked
      pantry_name, pantry_quantity, pantry_unit  (only when in_pantry)
      used         - the amount to pre-fill, in the pantry's unit ("" if units differ)
    """
    pantry_by_id = {item["id"]: item for item in pantry_items}
    rows = []
    for index, ingredient in enumerate(checked_recipe["ingredients"]):
        if ingredient["status"] == "assumed":
            continue

        row = {
            "index": index,
            "name": ingredient["name"],
            "recipe_amount": format_quantity(ingredient["amount"]),
            "recipe_unit": ingredient["unit"],
        }
        pantry_item = pantry_by_id.get(ingredient.get("pantry_item_id"))

        if pantry_item is None:
            row.update(in_pantry=False, have=False)
        else:
            units_match = same_unit(ingredient["unit"], pantry_item["unit"])
            row.update(
                in_pantry=True,
                have=True,
                pantry_name=pantry_item["name"],
                pantry_quantity=format_quantity(pantry_item["quantity"]),
                pantry_unit=pantry_item["unit"],
                used=format_quantity(ingredient["amount"]) if units_match else "",
            )
        rows.append(row)
    return rows


def _read_amount(text):
    """Turn "200" or "0,5" into a number. Blank means 0. Returns None if it isn't a number."""
    text = text.strip().replace(",", ".")
    if text == "":
        return 0.0
    try:
        amount = float(text)
    except ValueError:
        return None
    return amount if amount >= 0 else None


def apply_cooking(checked_recipe, pantry_items, form):
    """
    Work out what cooking this recipe changes.

    `form` holds your answers: "have_<index>" is present when a box is ticked,
    and "used_<index>" is the amount used, in the pantry's unit.

    Returns three things:
      changes - {pantry item id: new quantity}, or None as the quantity to remove the item
      to_buy  - a list like ["200 g Pecorino", "1 bunches Fresh basil"]
      errors  - messages about amounts that aren't numbers (nothing changes if there are any)
    """
    pantry_by_id = {item["id"]: item for item in pantry_items}
    used_per_item = {}
    to_buy = []
    errors = []

    for row in cook_checklist(checked_recipe, pantry_items):
        index = row["index"]
        has_it = form.get(f"have_{index}") is not None
        shopping_line = f"{row['recipe_amount']} {row['recipe_unit']} {row['name']}".replace("  ", " ")

        if not has_it:
            to_buy.append(shopping_line)
            continue

        if row["in_pantry"]:
            amount = _read_amount(form.get(f"used_{index}", ""))
            if amount is None:
                errors.append(f"Please check the amount used for {row['name']}.")
                continue
            pantry_id = checked_recipe["ingredients"][index]["pantry_item_id"]
            # The same pantry item can appear twice in a recipe (garlic in the sauce and on top).
            used_per_item[pantry_id] = used_per_item.get(pantry_id, 0.0) + amount

    changes = {}
    for pantry_id, used in used_per_item.items():
        if used == 0:
            continue
        left = pantry_by_id[pantry_id]["quantity"] - used
        changes[pantry_id] = None if left <= 0.0001 else round(left, 3)

    if errors:
        return {}, to_buy, errors
    return changes, to_buy, errors
