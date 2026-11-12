"""
A quick real-world check that Pantry Chef can talk to Claude.

Run on PythonAnywhere (scripts/deploy.py does this with --smoke). It uses the app's own
key from .env and makes real, paid requests:
  recipes  - one suggestion request with a small pretend pantry   (about 5-10 cents)
  photos   - reads a pretend receipt drawn by this script          (about 2-4 cents)
  tidy     - tidies up a messy pasted recipe                       (about 1-3 cents)
  all      - all three

It never touches your real pantry or recipes.
"""

import io
import os
import sys

from dotenv import load_dotenv

PROJECT_FOLDER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_FOLDER)
load_dotenv(os.path.join(PROJECT_FOLDER, ".env"))

import ai_client  # noqa: E402  (must come after the .env is loaded)
from photos import prepare_upload  # noqa: E402
from recipes import build_request, check_against_pantry, read_filters  # noqa: E402

PRETEND_PANTRY = [
    {"id": 1, "name": "Spaghetti", "category": "Dry pantry", "quantity": 500.0, "unit": "g", "expiry_date": None},
    {"id": 2, "name": "Cherry tomatoes", "category": "Vegetables", "quantity": 250.0, "unit": "g", "expiry_date": None},
    {"id": 3, "name": "Garlic", "category": "Vegetables", "quantity": 4.0, "unit": "pieces", "expiry_date": None},
    {"id": 4, "name": "Parmesan", "category": "Dairy", "quantity": 100.0, "unit": "g", "expiry_date": None},
]

RECEIPT_LINES = ["CORNER SHOP", "", "MILK 1L x2      2.40", "BANANAS 6       1.10",
                 "WASHING UP LIQ  1.99", "", "TOTAL           5.49"]


def check_recipes():
    """Ask Claude for real suggestions and check they look like recipes that use the pantry."""
    request_text = build_request(PRETEND_PANTRY, read_filters({"cuisine": "Italian", "people": "2"}))
    recipes = ai_client.suggest_recipes(request_text)
    problems = []
    if not 1 <= len(recipes) <= 3:
        problems.append(f"expected 1-3 recipes, got {len(recipes)}")
    for recipe in recipes:
        checked = check_against_pantry(recipe, PRETEND_PANTRY)
        used = [i["name"] for i in checked["ingredients"] if i["status"] in ("have", "low")]
        print(f"  - {recipe['title']} ({recipe['dish_type']}, {recipe['total_minutes']} min, "
              f"serves {recipe['servings']}): uses {', '.join(used) or 'nothing'} from the pantry; "
              f"missing {', '.join(checked['missing']) or 'nothing'}")
        if not recipe["steps"]:
            problems.append(f"{recipe['title']} has no steps")
        if not used:
            problems.append(f"{recipe['title']} uses nothing from the pantry")
    return problems


def check_photos():
    """Draw a simple receipt and check Claude finds the food and skips the washing-up liquid."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (900, 600), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    for number, line in enumerate(RECEIPT_LINES):
        draw.text((40, 30 + number * 75), line, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, format="PNG")

    items = ai_client.read_items_from_photos([prepare_upload(output.getvalue(), "receipt.png")])
    for item in items:
        print(f"  - {item['name']} · {item['category']} · {item['quantity']:g} {item['unit']}")
    names = " ".join(item["name"].lower() for item in items)
    problems = []
    if "milk" not in names:
        problems.append("milk wasn't found on the receipt")
    if "banana" not in names:
        problems.append("bananas weren't found on the receipt")
    if "washing" in names or "liquid" in names:
        problems.append("washing-up liquid should have been skipped")
    return problems


MESSY_RECIPE = """Quick pepper pasta (serves 2)
1 red pepper, cut into chunks
2 cloves of garlic crushed
200g penne
salt and pepper
olive oil

fry pepper + garlic in oil 10 mins, boil pasta, mix, season"""


def check_tidy():
    """Tidy a messy recipe and check ingredients come out as basic names with notes."""
    details = ai_client.tidy_recipe("Quick pepper pasta", MESSY_RECIPE)
    for ingredient in details["ingredients"]:
        note = f" ({ingredient['note']})" if ingredient["note"] else ""
        print(f"  - {ingredient['amount']:g} {ingredient['unit']} {ingredient['name']}{note}")
    for number, step in enumerate(details["steps"], start=1):
        print(f"    {number}. {step}")
    names = {ingredient["name"].lower(): ingredient for ingredient in details["ingredients"]}
    problems = []
    if "red pepper" not in names:
        problems.append("'1 red pepper, cut into chunks' should become 'Red pepper'")
    elif "chunk" not in names["red pepper"]["note"].lower():
        problems.append("'cut into chunks' should be kept as a note")
    if "garlic" not in names:
        problems.append("'2 cloves of garlic crushed' should become 'Garlic'")
    if not any("salt" in name for name in names) or not any("black pepper" in name or name == "pepper" for name in names):
        problems.append("'salt and pepper' should be split into two ingredients")
    if details["servings"] != 2:
        problems.append(f"servings should be 2, got {details['servings']}")
    if len(details["steps"]) < 2:
        problems.append("the method should be split into steps")
    return problems


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "recipes"
    problems = []
    try:
        if what in ("recipes", "all"):
            print("Real suggestion test:")
            problems += check_recipes()
        if what in ("photos", "all"):
            print("Real receipt-reading test:")
            problems += check_photos()
        if what in ("tidy", "all"):
            print("Real recipe-tidying test:")
            problems += check_tidy()
    except ai_client.SuggestionError as error:
        problems.append(str(error))

    if problems:
        print("SMOKE TEST FAILED: " + "; ".join(problems))
        sys.exit(1)
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
