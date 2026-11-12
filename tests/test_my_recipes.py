"""Tests for tidying up My recipes and cooking them, using a pretend Claude."""

import pytest

import ai_client
from app import create_app
from recipes import details_from_suggestion, ingredient_words, match_to_pantry, recipe_for_cooking, recipe_to_text

PANTRY = [
    {"id": 1, "name": "Red peppers", "category": "Vegetables", "quantity": 3.0, "unit": "pieces", "expiry_date": None},
    {"id": 2, "name": "Tomatoes", "category": "Vegetables", "quantity": 6.0, "unit": "pieces", "expiry_date": None},
    {"id": 3, "name": "Chicken", "category": "Proteins", "quantity": 500.0, "unit": "g", "expiry_date": None},
    {"id": 4, "name": "Penne", "category": "Dry pantry", "quantity": 500.0, "unit": "g", "expiry_date": None},
]

TIDIED = {
    "title": "Veg pasta bake",
    "summary": "A cheesy baked pasta.",
    "cuisine": "Italian",
    "difficulty": "Easy",
    "dish_type": "Main",
    "style": "Comfort",
    "total_minutes": 45,
    "servings": 4,
    "ingredients": [
        {"name": "Red pepper", "amount": 1, "unit": "pieces", "note": "cut into chunks", "is_staple": False},
        {"name": "Penne", "amount": 300, "unit": "g", "note": "", "is_staple": False},
        {"name": "Mozzarella", "amount": 125, "unit": "g", "note": "torn", "is_staple": False},
        {"name": "Salt", "amount": 1, "unit": "tsp", "note": "", "is_staple": True},
    ],
    "steps": ["Heat the oven to 200°C.", "Roast the pepper for 20 minutes.", "Mix with the pasta and bake."],
}

PASTED = "1 red pepper, cut into chunks\n300g penne\n1 ball mozzarella, torn\nRoast, mix, bake."


# --- Matching ingredients to the pantry ------------------------------------------

def test_ingredient_words_ignore_plurals_and_case():
    assert ingredient_words("Red Peppers") == ingredient_words("red pepper") == {"red", "pepper"}
    assert ingredient_words("Cherry tomatoes") == {"cherry", "tomato"}
    assert ingredient_words("Berries") == {"berry"}


def test_match_to_pantry():
    assert match_to_pantry("Red pepper", PANTRY)["id"] == 1            # same words
    assert match_to_pantry("Cherry tomatoes", PANTRY)["id"] == 2       # pantry "Tomatoes" is inside
    assert match_to_pantry("Chicken thighs", PANTRY)["id"] == 3        # pantry "Chicken" is inside
    assert match_to_pantry("Mozzarella", PANTRY) is None
    assert match_to_pantry("Pepper", PANTRY)["id"] == 1                # "pepper" is inside "red pepper"
    assert match_to_pantry("Black pepper", PANTRY) is None             # a staple, never the red peppers


def test_exact_matches_beat_partial_ones():
    pantry = [{"id": 1, "name": "Tomato puree"}, {"id": 2, "name": "Tomatoes"}]
    assert match_to_pantry("Tomato", pantry)["id"] == 2


def test_recipe_for_cooking_links_ingredients_and_marks_it_as_mine():
    recipe = recipe_for_cooking(TIDIED, 9, PANTRY)
    assert recipe["from_my_recipe_id"] == 9
    assert [i["pantry_item_id"] for i in recipe["ingredients"]] == [1, 4, None, None]
    assert recipe["ingredients"][0]["note"] == "cut into chunks"
    assert TIDIED["ingredients"][0].get("pantry_item_id") is None   # the original isn't changed


def test_details_from_suggestion_keeps_the_recipe_and_adds_notes():
    suggestion = dict(TIDIED, ingredients=[{"name": "Penne", "amount": 300, "unit": "g",
                                            "pantry_item_id": 4, "is_staple": False}])
    details = details_from_suggestion(suggestion)
    assert details["ingredients"] == [{"name": "Penne", "amount": 300, "unit": "g", "note": "", "is_staple": False}]
    assert details["steps"] == TIDIED["steps"]


def test_recipe_text_includes_ingredient_notes():
    assert "- 1 pieces Red pepper, cut into chunks" in recipe_to_text(TIDIED)


# --- The pages ----------------------------------------------------------------

class PretendTidy:
    def __init__(self, result=None, error=None):
        self.result = result or TIDIED
        self.error = error
        self.calls = []

    def __call__(self, title, text):
        self.calls.append((title, text))
        if self.error:
            raise ai_client.SuggestionError(self.error)
        return dict(self.result, title="Claude's title")


class PretendSuggest:
    def __init__(self):
        self.requests = []

    def __call__(self, request_text):
        self.requests.append(request_text)
        return []


def make_client(tmp_path, tidy=None, suggest=None):
    app = create_app(db_path=tmp_path / "test.db", password="pw",
                     suggest_recipes=suggest or PretendSuggest(), read_photo_items=lambda photos: [],
                     tidy_recipe=tidy or PretendTidy())
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    for name, category, quantity, unit in [("Red peppers", "Vegetables", "3", "pieces"),
                                           ("Penne", "Dry pantry", "500", "g")]:
        client.post("/items/new", data={"name": name, "category": category,
                                        "quantity": quantity, "unit": unit, "expiry_date": ""})
    return client


def test_pasted_recipes_are_tidied_and_keep_the_original(tmp_path):
    tidy = PretendTidy()
    client = make_client(tmp_path, tidy=tidy)

    page = client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED}, follow_redirects=True)

    assert tidy.calls == [("Veg pasta bake", PASTED)]
    assert b"and tidied it up" in page.data
    assert b"<strong>Red pepper</strong>" in page.data
    assert b"cut into chunks" in page.data
    assert b"Show original" in page.data
    assert b"1 ball mozzarella, torn" in page.data          # the original text
    assert b"<h1>Veg pasta bake</h1>" in page.data           # your title, not Claude's


def test_if_tidying_fails_the_recipe_is_still_saved(tmp_path):
    client = make_client(tmp_path, tidy=PretendTidy(error="Couldn't reach Anthropic."))
    page = client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED}, follow_redirects=True)

    assert b"couldn&#39;t be tidied up" in page.data
    assert b"Tidy up</button>" in page.data
    assert b"1 ball mozzarella, torn" in page.data
    assert b"Not tidied yet" in client.get("/my-recipes").data


def test_tidy_up_button_tidies_an_older_recipe(tmp_path):
    tidy = PretendTidy(error="Couldn't reach Anthropic.")
    client = make_client(tmp_path, tidy=tidy)
    client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED})

    tidy.error = None
    page = client.post("/my-recipes/1/tidy", follow_redirects=True)

    assert b"<strong>Red pepper</strong>" in page.data
    assert b"Cook this" in page.data


def test_cooking_my_recipe_uses_the_normal_cook_flow(tmp_path):
    client = make_client(tmp_path)
    client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED})

    page = client.post("/my-recipes/1/cook", follow_redirects=True)

    assert b"What did you use?" in page.data
    assert b"From my recipes" in page.data
    assert b'href="/my-recipes/1">\xe2\x86\x90 Back to the recipe' in page.data
    assert b"You have 3 pieces (Red peppers)." in page.data        # matched despite the plural
    assert b"Not in your pantry" in page.data                     # mozzarella
    assert b"(cut into chunks)" in page.data

    client.post("/recipes/1/cook", data={"have_0": "on", "used_0": "1", "have_1": "on", "used_1": "300"})
    pantry = client.get("/").data
    assert b"2 pieces" in pantry and b"200 g" in pantry
    assert b"last cooked today" in client.get("/my-recipes").data


def test_suggestions_send_claude_the_tidied_text(tmp_path):
    suggest = PretendSuggest()
    client = make_client(tmp_path, suggest=suggest)
    client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED})

    client.post("/suggest", data={})

    assert "- 1 pieces Red pepper, cut into chunks" in suggest.requests[0]
    assert "1 ball mozzarella" not in suggest.requests[0]


def test_starring_a_suggestion_needs_no_tidying(tmp_path):
    tidy = PretendTidy()
    suggestion = dict(TIDIED, from_my_recipe_id=None,
                      ingredients=[dict(i, pantry_item_id=None) for i in TIDIED["ingredients"]])
    app = create_app(db_path=tmp_path / "test.db", password="pw",
                     suggest_recipes=lambda text: [suggestion], tidy_recipe=tidy)
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    client.post("/items/new", data={"name": "Penne", "category": "Dry pantry",
                                    "quantity": "500", "unit": "g", "expiry_date": ""})
    client.post("/suggest", data={})

    client.post("/recipes/1/save", data={"back": "recipe"})

    assert tidy.calls == []
    assert b"Cook this" in client.get("/my-recipes/1").data


def test_deleting_a_recipe_removes_its_tidy_version(tmp_path):
    client = make_client(tmp_path)
    client.post("/my-recipes", data={"title": "Veg pasta bake", "text": PASTED})
    client.post("/my-recipes/1/delete")
    assert client.post("/my-recipes/1/cook").status_code == 404


def test_tidy_recipe_sends_the_right_settings(monkeypatch):
    calls = {}

    class FakeAnthropic:
        def __init__(self):
            self.beta = self
            self.messages = self

        def parse(self, **settings):
            calls.update(settings)

            class Response:
                stop_reason = "end_turn"
                parsed_output = ai_client.TidyRecipe(**TIDIED)
            return Response()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(ai_client.anthropic, "Anthropic", FakeAnthropic)

    result = ai_client.tidy_recipe("Veg pasta bake", PASTED)

    assert result["ingredients"][0]["name"] == "Red pepper"
    assert calls["output_format"] is ai_client.TidyRecipe
    assert calls["output_config"] == {"effort": "low"}
    assert calls["messages"][0]["content"].startswith("Title: Veg pasta bake")


def test_claude_must_give_a_known_dish_type_when_tidying():
    with pytest.raises(ValueError):
        ai_client.TidyRecipe(**dict(TIDIED, dish_type="Snack"))
