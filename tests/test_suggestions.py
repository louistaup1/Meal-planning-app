"""Tests for the dinner suggestion pages, using a pretend Claude."""

import pytest

import ai_client
from app import create_app

PRETEND_RECIPE = {
    "title": "Garlic spaghetti",
    "summary": "Simple and fast.",
    "cuisine": "Italian",
    "difficulty": "Easy",
    "style": "Quick",
    "total_minutes": 20,
    "servings": 2,
    "ingredients": [
        {"name": "Spaghetti", "amount": 200, "unit": "g", "pantry_item_id": 1, "is_staple": False},
        {"name": "Salt", "amount": 1, "unit": "tsp", "pantry_item_id": None, "is_staple": True},
        {"name": "Fresh parsley", "amount": 1, "unit": "bunches", "pantry_item_id": None, "is_staple": False},
    ],
    "steps": ["Boil the pasta.", "Toss with parsley."],
}


class PretendClaude:
    """Stands in for ai_client.suggest_recipes and remembers what it was asked."""

    def __init__(self, recipes=None, error=None):
        self.recipes = recipes if recipes is not None else [PRETEND_RECIPE]
        self.error = error
        self.requests = []

    def __call__(self, request_text):
        self.requests.append(request_text)
        if self.error:
            raise ai_client.SuggestionError(self.error)
        return self.recipes


def make_client(tmp_path, pretend):
    app = create_app(db_path=tmp_path / "test.db", password="pw", suggest_recipes=pretend)
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    return client


def add_spaghetti(client):
    client.post("/items/new", data={"name": "Spaghetti", "category": "Dry pantry",
                                    "quantity": "500", "unit": "g", "expiry_date": ""})


def test_empty_pantry_does_not_call_claude(tmp_path):
    pretend = PretendClaude()
    client = make_client(tmp_path, pretend)
    page = client.post("/suggest", data={})
    assert b"Your pantry is empty" in page.data
    assert pretend.requests == []


def test_suggestions_show_missing_ingredients_and_respect_filters(tmp_path):
    pretend = PretendClaude()
    client = make_client(tmp_path, pretend)
    add_spaghetti(client)

    page = client.post("/suggest", data={"cuisine": "Italian", "difficulty": "Any", "style": "Quick"})

    assert b"Garlic spaghetti" in page.data
    assert b"20 min" in page.data
    # Salt is a staple, so only parsley is missing.
    assert b"missing: Fresh parsley" in page.data
    assert "Cuisine: Italian" in pretend.requests[0]
    assert "Spaghetti, 500 g" in pretend.requests[0]


def test_only_three_suggestions_are_shown(tmp_path):
    many = [dict(PRETEND_RECIPE, title=f"Recipe {n}") for n in range(5)]
    client = make_client(tmp_path, PretendClaude(recipes=many))
    add_spaghetti(client)
    page = client.post("/suggest", data={})
    assert page.data.count(b'class="recipe-card"') == 3


def test_problems_are_shown_as_friendly_messages(tmp_path):
    client = make_client(tmp_path, PretendClaude(error="Couldn't reach Anthropic."))
    add_spaghetti(client)
    page = client.post("/suggest", data={})
    assert b"Couldn&#39;t reach Anthropic." in page.data


def test_recipe_page_shows_steps_and_what_to_buy(tmp_path):
    client = make_client(tmp_path, PretendClaude())
    add_spaghetti(client)
    client.post("/suggest", data={})

    page = client.get("/recipes/1")
    assert b"Boil the pasta." in page.data
    assert b"to buy" in page.data
    assert client.get("/recipes/999").status_code == 404


# --- ai_client, with a fake Anthropic library ---------------------------------

class FakeResponse:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class FakeAnthropic:
    """Replaces anthropic.Anthropic so no real request is ever sent."""
    last_call = None
    response = None

    def __init__(self):
        self.beta = self
        self.messages = self

    def parse(self, **settings):
        FakeAnthropic.last_call = settings
        return FakeAnthropic.response


@pytest.fixture
def fake_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(ai_client.anthropic, "Anthropic", FakeAnthropic)
    return FakeAnthropic


def test_missing_api_key_gives_a_clear_message(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ai_client.SuggestionError, match="No Anthropic API key"):
        ai_client.suggest_recipes("anything")


def test_suggest_recipes_sends_the_right_settings_and_returns_dicts(fake_anthropic):
    recipe = ai_client.Recipe(**PRETEND_RECIPE)
    fake_anthropic.response = FakeResponse(ai_client.Suggestions(recipes=[recipe]))

    recipes = ai_client.suggest_recipes("My pantry: ...")

    call = fake_anthropic.last_call
    assert call["model"] == "claude-opus-5-5"
    assert call["fallbacks"] == "default"
    assert call["output_format"] is ai_client.Suggestions
    assert call["messages"] == [{"role": "user", "content": "My pantry: ..."}]
    assert recipes[0]["title"] == "Garlic spaghetti"
    assert recipes[0]["ingredients"][0]["pantry_item_id"] == 1


def test_a_refusal_becomes_a_friendly_error(fake_anthropic):
    fake_anthropic.response = FakeResponse(None, stop_reason="refusal")
    with pytest.raises(ai_client.SuggestionError, match="couldn't suggest"):
        ai_client.suggest_recipes("My pantry: ...")
