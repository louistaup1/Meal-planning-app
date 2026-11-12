"""
Talking to Claude.

This is the only file that calls the Anthropic API. It sends the request
written by recipes.build_request() and gets back recipes in a fixed format,
so the rest of the app never has to guess what Claude meant.

Your API key is read from the ANTHROPIC_API_KEY line in the .env file.
"""

import base64
import os
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel

from pantry import CATEGORIES

# The Claude model used for suggestions. Change this one line to switch models.
MODEL = "claude-opus-5-5"


# --- The exact shape we ask Claude to reply in --------------------------------

class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str
    pantry_item_id: Optional[int]  # which pantry item this uses, or None
    is_staple: bool                # salt, black pepper, cooking oil


class Recipe(BaseModel):
    title: str
    summary: str
    cuisine: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    dish_type: Literal["Main", "Starter", "Side", "Dessert"]
    style: str
    total_minutes: int
    servings: int
    ingredients: list[Ingredient]
    steps: list[str]
    from_my_recipe_id: Optional[int]  # set when it's one of "My saved recipes"


class Suggestions(BaseModel):
    recipes: list[Recipe]


class PhotoItem(BaseModel):
    name: str
    category: Literal[tuple(CATEGORIES)]  # one of the pantry categories
    quantity: float
    unit: str


class PhotoItems(BaseModel):
    items: list[PhotoItem]


INSTRUCTIONS = """You are a friendly home-cooking assistant. You suggest recipes \
based on what the person already has in their pantry.

How to choose recipes:
- Build each recipe mostly from pantry items, so the person has to buy as little as possible.
- Prefer items marked EXPIRES SOON, so they don't go to waste. Never use items marked EXPIRED.
- Respect every preference given (meal, dish type, cuisine, difficulty, style).
  "Quick" means 30 minutes or less in total.
- Suit the meal: for example, breakfast recipes should be things people eat at breakfast.
- Set dish_type to what each recipe is: Main, Starter, Side or Dessert. If a dish type was asked
  for, every recipe must be that type.
- Make the recipes different from each other.
- Write each recipe for the number of people asked for, and scale the ingredient amounts to match.
  Set servings to that number.

How to fill in each ingredient:
- pantry_item_id: the id of the pantry item it uses, exactly as listed. Use null if it's not in the pantry.
- When an ingredient comes from the pantry, use the same unit as the pantry item where it makes sense.
- is_staple: true only for salt, black pepper, and plain cooking oil. Don't list water.

How to write the steps:
- Short, clear steps a beginner can follow, one action per step. Don't number them.
- Include temperatures in °C and times in minutes.

total_minutes is the total time, including preparation.

The person may also share "My saved recipes". Treat them as options alongside new ideas, \
with no special priority. When you suggest one of them, set from_my_recipe_id to its id \
and follow it closely (you may scale amounts for the number of people, and use the pantry's \
units). Otherwise set from_my_recipe_id to null."""


class TidyIngredient(BaseModel):
    name: str        # the basic ingredient, as it would be called in a pantry: "Red pepper"
    amount: float
    unit: str
    note: str        # preparation or extra detail: "cut into chunks", "" if none
    is_staple: bool  # salt, black pepper, cooking oil


class TidyRecipe(BaseModel):
    title: str
    summary: str
    cuisine: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    dish_type: Literal["Main", "Starter", "Side", "Dessert"]
    style: str
    total_minutes: int
    servings: int
    ingredients: list[TidyIngredient]
    steps: list[str]


TIDY_INSTRUCTIONS = """You tidy up recipes that someone pasted into their cooking app, so the app \
can check the ingredients against their pantry and guide them step by step.

Stay faithful to the recipe. Don't add ingredients or steps that aren't there, and don't change
amounts. Just put everything into the standard format.

Ingredients:
- name: the basic ingredient, the way it would be written on a shopping list or pantry shelf,
  in sentence case. "1 red pepper, cut into chunks" has name "Red pepper".
  "2 cloves of garlic, crushed" has name "Garlic". "200g tinned chopped tomatoes" has name
  "Chopped tomatoes".
- note: how it's prepared or any extra detail ("cut into chunks", "crushed", "optional").
  Use "" when there's nothing to add.
- amount and unit: as given. Prefer these units: pieces, g, kg, ml, L, tbsp, tsp, cans, jars,
  packs, bunches. "2 cloves of garlic" is amount 2, unit "pieces". If no amount is given
  (for example "a pinch of salt"), use your best small estimate and say so in the note.
- One ingredient per line. Split "salt and pepper" into two.
- is_staple: true only for salt, black pepper and plain cooking oil.

Steps: the recipe's own method, one clear action per step, without numbers. Keep the
temperatures and times it gives; convert Fahrenheit to Celsius.

If the recipe doesn't say, give your best estimate for total_minutes, servings, difficulty,
cuisine, dish_type and style (Quick, Comfort or Healthy). Write a one-sentence summary."""


class SuggestionError(Exception):
    """A problem getting suggestions, with a message that's safe to show on screen."""


PHOTO_INSTRUCTIONS = """You help someone fill in their kitchen pantry app from photos.

The photos may show a shop receipt, fridge or cupboard shelves, spice jars, or shopping bags.
You may also get PDFs, usually receipts or order confirmations from online grocery shopping.
List every food or drink item you can identify, so it can be added to the pantry.

For each item:
- name: a short, friendly name in sentence case, for example "Cherry tomatoes" or "Smoked paprika".
  Receipts use abbreviations ("ORG CHRY TOM 250G"); write the full everyday name instead.
  Leave out brand names unless they matter (for example "Greek yogurt", not "Fage Total 0%").
- category: the best fit from the list given.
- quantity and unit: how much there is.
  - On a receipt, use the size and how many were bought. "MILK 1L x2" is quantity 2, unit "L".
    If only a count is shown, use "pieces", "packs", "cans" or "jars" as fits.
  - On shelves or in photos of jars, count what you can see, for example 3 "jars" or 6 "pieces".
  - Prefer these units: pieces, g, kg, ml, L, cans, jars, packs, bunches.

Other rules:
- Skip anything that isn't food or drink (cleaning products, toiletries, bags, discounts, totals,
  delivery fees). In an online order, skip items marked as unavailable or substituted away.
- If the same item appears more than once, list it once with the total quantity.
- Skip anything you can't read or recognise clearly. Don't guess."""


def suggest_recipes(request_text):
    """
    Ask Claude for recipe suggestions.

    Returns a list of plain dictionaries, one per recipe.
    Raises SuggestionError with a friendly message if something goes wrong.
    """
    result = _ask_claude(
        instructions=INSTRUCTIONS,
        content=request_text,
        output_format=Suggestions,
        effort="medium",
    )
    return [recipe.model_dump() for recipe in result.recipes]


def read_items_from_photos(uploads):
    """
    Ask Claude which food items it can see in photos and PDFs:
    receipts, shelves, spice jars and so on.
    `uploads` comes from photos.prepare_upload(): each has a media_type and data.
    Returns a list of dictionaries with name, category, quantity and unit.
    """
    content = []
    for upload in uploads:
        # Claude reads PDFs as "document" blocks and photos as "image" blocks.
        block_type = "document" if upload["media_type"] == "application/pdf" else "image"
        content.append({
            "type": block_type,
            "source": {
                "type": "base64",
                "media_type": upload["media_type"],
                "data": base64.standard_b64encode(upload["data"]).decode("utf-8"),
            },
        })
    categories = ", ".join(CATEGORIES)
    content.append({
        "type": "text",
        "text": f"Which food items can you see in these photos or documents? Categories to choose from: {categories}.",
    })

    result = _ask_claude(
        instructions=PHOTO_INSTRUCTIONS,
        content=content,
        output_format=PhotoItems,
        effort="medium",
    )
    return [item.model_dump() for item in result.items]


def tidy_recipe(title, text):
    """
    Turn a pasted recipe into the app's standard format (a dictionary like a suggestion,
    with a "note" on each ingredient). Raises SuggestionError if something goes wrong.
    """
    result = _ask_claude(
        instructions=TIDY_INSTRUCTIONS,
        content=f"Title: {title}\n\n{text}",
        output_format=TidyRecipe,
        effort="low",
    )
    return result.model_dump()


def _ask_claude(instructions, content, output_format, effort):
    """
    Send one request to Claude and return its reply in the given format.
    All the error handling for every Claude request lives here.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SuggestionError(
            "No Anthropic API key found. Add ANTHROPIC_API_KEY to your .env file, "
            "then reload the app."
        )

    client = anthropic.Anthropic()

    try:
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": effort},
            # If Claude declines for safety reasons (very unlikely for recipes),
            # Anthropic automatically retries with a recommended backup model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=instructions,
            messages=[{"role": "user", "content": content}],
            output_format=output_format,
        )
    except anthropic.AuthenticationError:
        raise SuggestionError("Anthropic didn't accept the API key. Check ANTHROPIC_API_KEY in your .env file.")
    except anthropic.PermissionDeniedError:
        raise SuggestionError("Your Anthropic account can't use this model yet. Check your account in the Anthropic console.")
    except anthropic.RateLimitError:
        raise SuggestionError("Too many requests right now. Wait a minute and try again.")
    except anthropic.APIStatusError as error:
        if error.status_code == 400 and "credit" in str(error.message).lower():
            raise SuggestionError("Your Anthropic account is out of credit. Add credit under Settings → Billing.")
        raise SuggestionError(f"Anthropic returned an error ({error.status_code}). Please try again in a moment.")
    except anthropic.APIConnectionError:
        raise SuggestionError("Couldn't reach Anthropic. Check the internet connection and try again.")

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise SuggestionError("Claude couldn't answer this time. Please try again.")

    return response.parsed_output
