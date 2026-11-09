"""
Pantry rules.

This file knows what a valid pantry item looks like, how to tell whether
an item is expiring soon, and how to group items by category.
It does not know anything about web pages or the database.
"""

from datetime import date


# The categories shown in the app, in the order they appear on the page.
CATEGORIES = [
    "Dry pantry",
    "Vegetables",
    "Fruits",
    "Spices",
    "Dairy",
    "Proteins",
    "Other",
]

# A little picture for each category, shown on the pantry page.
CATEGORY_EMOJI = {
    "Dry pantry": "🥫",
    "Vegetables": "🥕",
    "Fruits": "🍎",
    "Spices": "🌶️",
    "Dairy": "🧀",
    "Proteins": "🍗",
    "Other": "🧺",
}

# Common units, offered as suggestions in the form. You can still type any unit.
SUGGESTED_UNITS = ["pieces", "g", "kg", "ml", "L", "cans", "jars", "packs", "bunches", "tbsp", "tsp"]

# An item counts as "expiring soon" if it expires within this many days.
EXPIRING_SOON_DAYS = 3


def validate_item(form):
    """
    Check the values typed into the add/edit form.

    `form` is a dictionary like {"name": "Rice", "category": "Dry pantry", ...}.
    Returns two things:
      - a clean dictionary of the item's values
      - a list of error messages (empty if everything is fine)
    """
    errors = []

    name = form.get("name", "").strip()
    if name == "":
        errors.append("Please enter a name.")

    category = form.get("category", "").strip()
    if category not in CATEGORIES:
        errors.append("Please choose a category.")

    quantity_text = form.get("quantity", "").strip()
    quantity = None
    if quantity_text == "":
        errors.append("Please enter a quantity.")
    else:
        try:
            quantity = float(quantity_text.replace(",", "."))
        except ValueError:
            errors.append("Quantity must be a number, like 2 or 0.5.")
        else:
            if quantity < 0:
                errors.append("Quantity can't be negative.")

    unit = form.get("unit", "").strip()

    expiry_text = form.get("expiry_date", "").strip()
    expiry_date = None
    if expiry_text != "":
        try:
            expiry_date = date.fromisoformat(expiry_text)
        except ValueError:
            errors.append("Expiry date must be a real date.")

    item = {
        "name": name,
        "category": category,
        "quantity": quantity,
        "unit": unit,
        "expiry_date": expiry_date,
    }
    return item, errors


def expiry_status(expiry_date, today=None):
    """
    Say how fresh an item is.

    Returns one of:
      None        - no expiry date was set
      "expired"   - the date has passed
      "soon"      - expires today or within EXPIRING_SOON_DAYS days
      "ok"        - expires later than that
    """
    if expiry_date is None:
        return None
    if today is None:
        today = date.today()

    days_left = (expiry_date - today).days
    if days_left < 0:
        return "expired"
    if days_left <= EXPIRING_SOON_DAYS:
        return "soon"
    return "ok"


def format_quantity(quantity):
    """Show 2.0 as "2" and 0.5 as "0.5", so numbers look natural."""
    if quantity == int(quantity):
        return str(int(quantity))
    return str(round(quantity, 2))


def group_by_category(items):
    """
    Put items into their categories, in the order of CATEGORIES.

    Returns a list of (category name, list of items) pairs.
    Empty categories are left out. Items are sorted by name.
    """
    groups = []
    for category in CATEGORIES:
        items_in_category = [item for item in items if item["category"] == category]
        if items_in_category:
            items_in_category.sort(key=lambda item: item["name"].lower())
            groups.append((category, items_in_category))
    return groups


def find_by_name(name, pantry_items):
    """Find a pantry item with the same name, ignoring capital letters. Returns None if there isn't one."""
    key = name.strip().lower()
    for item in pantry_items:
        if item["name"].strip().lower() == key:
            return item
    return None


def same_unit(unit_a, unit_b):
    return unit_a.strip().lower() == unit_b.strip().lower()


def plan_photo_additions(found_items, pantry_items):
    """
    Tidy up the items Claude found in photos, ready for you to review.

    - Fixes anything odd (unknown category becomes "Other", a missing quantity becomes 1).
    - Combines duplicates with the same name and unit.
    - Compares with your pantry:
        same name and unit   -> ticked, will top up the existing item
        same name, new unit  -> unticked, with a note, so you decide
        not in pantry        -> ticked, will be added
    Returns a list of dictionaries: name, category, quantity, unit, include, note.
    """
    combined = []
    for found in found_items:
        name = str(found.get("name", "")).strip()[:100]
        if name == "":
            continue
        category = found.get("category") if found.get("category") in CATEGORIES else "Other"
        try:
            quantity = float(found.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 1.0
        if quantity <= 0:
            quantity = 1.0
        unit = str(found.get("unit", "")).strip()[:20]

        duplicate = next(
            (c for c in combined if c["name"].lower() == name.lower() and same_unit(c["unit"], unit)),
            None,
        )
        if duplicate:
            duplicate["quantity"] += quantity
        else:
            combined.append({"name": name, "category": category, "quantity": quantity, "unit": unit})

    plan = []
    for item in combined:
        existing = find_by_name(item["name"], pantry_items)
        if existing is None:
            item["include"] = True
            item["note"] = ""
        elif same_unit(existing["unit"], item["unit"]):
            item["include"] = True
            item["note"] = (f"You have {format_quantity(existing['quantity'])} {existing['unit']}. "
                            "This will be added to it.")
        else:
            item["include"] = False
            item["note"] = (f"Already in your pantry as {format_quantity(existing['quantity'])} "
                            f"{existing['unit']}. Tick to add it as a separate item.")
        item["quantity"] = format_quantity(item["quantity"])
        plan.append(item)
    return plan


def top_up_target(item, pantry_items):
    """
    If the pantry already has this item with the same unit, return that pantry item,
    so we add to its quantity instead of creating a duplicate. Otherwise return None.
    """
    existing = find_by_name(item["name"], pantry_items)
    if existing is not None and same_unit(existing["unit"], item["unit"]):
        return existing
    return None
