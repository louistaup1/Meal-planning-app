"""
Recipe rules (no AI in here).

This file knows the filter choices, writes the request we send to Claude,
and checks each suggested recipe against your real pantry to find out
what you're missing. Because it doesn't talk to Claude, it's easy to test.
"""

from pantry import expiry_status, format_quantity


# Filter choices shown on the suggestions page. "Any" means no preference.
CUISINES = ["Any", "Italian", "French", "Asian", "Indian", "Mexican", "Mediterranean", "American"]
DIFFICULTIES = ["Any", "Easy", "Medium", "Hard"]
STYLES = ["Any", "Quick", "Comfort", "Healthy"]
PEOPLE_CHOICES = [1, 2, 3, 4, 5, 6, 7, 8]
DEFAULT_PEOPLE = 2

MAX_SUGGESTIONS = 3


def read_filters(form):
    """
    Read the filter choices from the form.
    Anything missing or unexpected becomes "Any", so a bad value can't break things.
    """
    filters = {}
    for field, choices in (("cuisine", CUISINES), ("difficulty", DIFFICULTIES), ("style", STYLES)):
        value = form.get(field, "Any")
        filters[field] = value if value in choices else "Any"

    try:
        people = int(form.get("people", DEFAULT_PEOPLE))
    except ValueError:
        people = DEFAULT_PEOPLE
    filters["people"] = people if people in PEOPLE_CHOICES else DEFAULT_PEOPLE
    return filters


def describe_pantry(pantry_items, today=None):
    """
    Turn the pantry into simple lines of text for Claude, one item per line, e.g.
      id 3: Milk, 1 L (Dairy), EXPIRES SOON on 2026-11-08
    """
    lines = []
    for item in pantry_items:
        line = f"id {item['id']}: {item['name']}, {format_quantity(item['quantity'])} {item['unit']}".rstrip()
        line += f" ({item['category']})"
        status = expiry_status(item["expiry_date"], today)
        if status == "soon":
            line += f", EXPIRES SOON on {item['expiry_date'].isoformat()}"
        elif status == "expired":
            line += f", EXPIRED on {item['expiry_date'].isoformat()} (don't use)"
        lines.append(line)
    return "\n".join(lines)


def build_request(pantry_items, filters, today=None):
    """Write the message we send to Claude: the pantry plus the filters."""
    wishes = []
    if filters["cuisine"] != "Any":
        wishes.append(f"Cuisine: {filters['cuisine']}")
    if filters["difficulty"] != "Any":
        wishes.append(f"Difficulty: {filters['difficulty']}")
    if filters["style"] != "Any":
        wishes.append(f"Style: {filters['style']}")
    wishes_text = "\n".join(wishes) if wishes else "No preferences. Surprise me."

    people = filters["people"]
    people_text = "1 person" if people == 1 else f"{people} people"

    return (
        f"Suggest up to {MAX_SUGGESTIONS} dinner recipes for tonight, for {people_text}.\n\n"
        f"My pantry:\n{describe_pantry(pantry_items, today)}\n\n"
        f"My preferences:\n{wishes_text}"
    )


def check_against_pantry(recipe, pantry_items):
    """
    Compare a recipe's ingredients with the pantry.

    Claude tells us which pantry item (by id) each ingredient uses, but we
    double-check that the id really exists. Returns a copy of the recipe where
    each ingredient has a "status":
      "have"     - it's in your pantry
      "low"      - it's in your pantry, same unit, but you have less than needed
      "assumed"  - a basic staple (like salt) that isn't listed; we assume you have it
      "missing"  - you need to buy it
    The recipe also gets a "missing" list with the names of what to buy.
    """
    pantry_by_id = {item["id"]: item for item in pantry_items}

    checked_ingredients = []
    missing = []
    for ingredient in recipe["ingredients"]:
        ingredient = dict(ingredient)
        pantry_item = pantry_by_id.get(ingredient.get("pantry_item_id"))

        if pantry_item is None:
            # Ignore ids that don't match a real pantry item.
            ingredient["pantry_item_id"] = None
            if ingredient.get("is_staple"):
                ingredient["status"] = "assumed"
            else:
                ingredient["status"] = "missing"
                missing.append(ingredient["name"])
        else:
            ingredient["pantry_name"] = pantry_item["name"]
            same_unit = ingredient["unit"].strip().lower() == pantry_item["unit"].strip().lower()
            if same_unit and ingredient["amount"] > pantry_item["quantity"]:
                ingredient["status"] = "low"
            else:
                ingredient["status"] = "have"

        checked_ingredients.append(ingredient)

    checked = dict(recipe)
    checked["ingredients"] = checked_ingredients
    checked["missing"] = missing
    return checked
