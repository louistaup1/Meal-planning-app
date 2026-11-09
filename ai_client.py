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
    style: str
    total_minutes: int
    servings: int
    ingredients: list[Ingredient]
    steps: list[str]
    from_my_recipe_id: Optional[int]  # set when it's one of "My saved recipes"


class Suggestions(BaseModel):
    recipes: list[Recipe]


class SpiceList(BaseModel):
    spices: list[str]


INSTRUCTIONS = """You are a friendly home-cooking assistant. You suggest dinner recipes \
based on what the person already has in their pantry.

How to choose recipes:
- Build each recipe mostly from pantry items, so the person has to buy as little as possible.
- Prefer items marked EXPIRES SOON, so they don't go to waste. Never use items marked EXPIRED.
- Respect every preference given (cuisine, difficulty, style). "Quick" means 30 minutes or less in total.
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


class SuggestionError(Exception):
    """A problem getting suggestions, with a message that's safe to show on screen."""


SPICE_INSTRUCTIONS = """You read spice labels from photos for a pantry app.

List every spice, dried herb, spice blend or seasoning whose label you can read in the photos.
- Use the common English name in sentence case, for example "Smoked paprika" or "Herbes de Provence".
- List each spice once, even if it appears in several photos.
- Skip anything you can't read clearly. Don't guess.
- Skip things that aren't spices or seasonings (for example oil, vinegar or flour)."""


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


def read_spices_from_photos(jpeg_photos):
    """
    Ask Claude which spices it can see in some photos (each one JPEG bytes).
    Returns a list of spice names.
    """
    content = []
    for photo in jpeg_photos:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(photo).decode("utf-8"),
            },
        })
    content.append({"type": "text", "text": "Which spices can you see in these photos?"})

    result = _ask_claude(
        instructions=SPICE_INSTRUCTIONS,
        content=content,
        output_format=SpiceList,
        effort="low",
    )
    return result.spices


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
