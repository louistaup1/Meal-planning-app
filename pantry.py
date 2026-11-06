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
