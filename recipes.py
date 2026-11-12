"""
Recipe rules (no AI in here).

This file knows the filter choices, writes the request we send to Claude,
and checks each suggested recipe against your real pantry to find out
what you're missing. Because it doesn't talk to Claude, it's easy to test.
"""

import re
from datetime import date, datetime

from pantry import expiry_status, format_quantity


# Filter choices shown on the suggestions page. "Any" means no preference.
CUISINES = ["Any", "Italian", "French", "Asian", "Indian", "Mexican", "Mediterranean", "American"]
DIFFICULTIES = ["Any", "Easy", "Medium", "Hard"]
STYLES = ["Any", "Quick", "Comfort", "Healthy"]
MEALS = ["Breakfast", "Lunch", "Dinner"]
DISH_TYPES = ["Any", "Main", "Starter", "Side", "Dessert"]
DEFAULT_MEAL = "Dinner"
DEFAULT_DISH_TYPE = "Main"

# How each dish type is written in the request to Claude.
DISH_TYPE_WORDS = {
    "Any": "recipes (any kind of dish)",
    "Main": "main dish recipes",
    "Starter": "starter recipes",
    "Side": "side dish recipes",
    "Dessert": "dessert recipes",
}
PEOPLE_CHOICES = [1, 2, 3, 4, 5, 6, 7, 8]
DEFAULT_PEOPLE = 2

MAX_SUGGESTIONS = 3

# A pasted recipe can be up to this many characters (about 3 pages of text).
MAX_MY_RECIPE_LENGTH = 10000


def read_filters(form):
    """
    Read the filter choices from the form.
    Anything missing or unexpected falls back to its default ("Any", Dinner, Main dish,
    2 people), so a bad value can't break things.
    """
    filters = {}
    meal = form.get("meal", DEFAULT_MEAL)
    filters["meal"] = meal if meal in MEALS else DEFAULT_MEAL
    dish_type = form.get("dish_type", DEFAULT_DISH_TYPE)
    filters["dish_type"] = dish_type if dish_type in DISH_TYPES else DEFAULT_DISH_TYPE

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


def validate_my_recipe(form):
    """
    Check a pasted recipe. Returns (title, text, errors).
    """
    title = form.get("title", "").strip()
    text = form.get("text", "").strip()
    errors = []
    if title == "":
        errors.append("Please give the recipe a title.")
    if text == "":
        errors.append("Please paste the recipe.")
    elif len(text) > MAX_MY_RECIPE_LENGTH:
        errors.append(f"That recipe is very long. Please keep it under {MAX_MY_RECIPE_LENGTH} characters.")
    return title, text, errors


def describe_my_recipes(my_recipes):
    """Turn your saved recipes into text for Claude, each with its id."""
    parts = []
    for recipe in my_recipes:
        parts.append(f"--- My recipe id {recipe['id']}: {recipe['title']} ---\n{recipe['text']}")
    return "\n\n".join(parts)


def link_to_my_recipe(recipe, my_recipes):
    """
    Claude says which of your saved recipes a suggestion comes from (or None).
    Keep that only if the id really is one of your saved recipes.
    """
    known_ids = {saved["id"] for saved in my_recipes}
    linked = dict(recipe)
    if linked.get("from_my_recipe_id") not in known_ids:
        linked["from_my_recipe_id"] = None
    return linked


def build_request(pantry_items, filters, today=None, my_recipes=()):
    """Write the message we send to Claude: the pantry, the filters, and your saved recipes."""
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
        f"Suggest up to {MAX_SUGGESTIONS} {DISH_TYPE_WORDS[filters['dish_type']]} "
        f"for {filters['meal'].lower()}, for {people_text}.\n\n"
        f"My pantry:\n{describe_pantry(pantry_items, today)}\n\n"
        f"My preferences:\n{wishes_text}"
        + (f"\n\nMy saved recipes:\n{describe_my_recipes(my_recipes)}" if my_recipes else "")
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


def recipe_to_text(recipe):
    """
    Write a suggested recipe out as plain text, ready to save in My recipes.
    Uses the recipe as Claude wrote it (amounts for the number of people it was made for).
    """
    facts = [f"Serves {recipe['servings']}", f"{recipe['total_minutes']} min", recipe["difficulty"], recipe["cuisine"]]
    if recipe.get("dish_type"):
        facts.append(recipe["dish_type"])

    lines = [" · ".join(facts), "", recipe["summary"], "", "Ingredients:"]
    for ingredient in recipe["ingredients"]:
        amount = f"{format_quantity(ingredient['amount'])} {ingredient['unit']}".strip()
        lines.append(f"- {amount} {ingredient['name']}")
    lines += ["", "Method:"]
    for number, step in enumerate(recipe["steps"], start=1):
        lines.append(f"{number}. {step}")
    return "\n".join(lines)


def mark_saved(recipe, my_recipe_ids):
    """
    Note on a suggested recipe whether it's in My recipes, so the page can show
    "⭐ In My recipes" instead of a Save button. A saved copy you've since deleted
    doesn't count, so the Save button comes back.
    """
    marked = dict(recipe)
    saved_id = recipe.get("saved_as_my_recipe_id")
    marked["saved_my_recipe_id"] = saved_id if saved_id in my_recipe_ids else None
    return marked



# --- "Cooked before" -----------------------------------------------------------

def title_key(title):
    """
    A simplified title for matching: lower case, no punctuation, single spaces.
    "Creamy Chicken & Tomato Spaghetti!" and "creamy chicken tomato spaghetti" match.
    """
    words = re.sub(r"[^a-z0-9]+", " ", title.lower()).split()
    return " ".join(word for word in words if word != "and")


def last_cooked_lookup(cooked_log):
    """
    From the cooking diary, the latest date for each recipe, found two ways:
    by My recipes id (exact) and by simplified title (for Claude's own ideas).
    """
    by_my_recipe, by_title = {}, {}
    for entry in cooked_log:  # oldest first, so later entries win
        when = datetime.fromisoformat(entry["cooked_at"]).date()
        by_title[title_key(entry["title"])] = when
        if entry["my_recipe_id"] is not None:
            by_my_recipe[entry["my_recipe_id"]] = when
    return by_my_recipe, by_title


def when_last_cooked(recipe, lookup):
    """The date this recipe was last cooked, or None. Works for suggestions and My recipes."""
    by_my_recipe, by_title = lookup
    for my_id in (recipe.get("from_my_recipe_id"), recipe.get("saved_as_my_recipe_id"), recipe.get("my_recipe_id")):
        if my_id is not None and my_id in by_my_recipe:
            return by_my_recipe[my_id]
    return by_title.get(title_key(recipe["title"]))


def format_cooked_date(when, today=None):
    """Show a date like "9 Nov", adding the year if it isn't this year."""
    if when is None:
        return ""
    today = today or date.today()
    if when == today:
        return "today"
    if when.year == today.year:
        return f"{when.day} {when.strftime('%b')}"
    return f"{when.day} {when.strftime('%b %Y')}"
