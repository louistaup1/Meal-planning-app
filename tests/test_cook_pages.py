"""Tests that click through the cook flow, using a pretend Claude."""

from app import create_app

RECIPE = {
    "title": "Garlic spaghetti",
    "summary": "Simple and fast.",
    "cuisine": "Italian",
    "difficulty": "Easy",
    "style": "Quick",
    "total_minutes": 20,
    "servings": 2,
    "ingredients": [
        {"name": "Spaghetti", "amount": 200, "unit": "g", "pantry_item_id": 1, "is_staple": False},
        {"name": "Garlic", "amount": 2, "unit": "pieces", "pantry_item_id": 2, "is_staple": False},
        {"name": "Salt", "amount": 1, "unit": "tsp", "pantry_item_id": None, "is_staple": True},
        {"name": "Fresh parsley", "amount": 1, "unit": "bunches", "pantry_item_id": None, "is_staple": False},
    ],
    "steps": ["Boil the pasta.", "Fry the garlic.", "Toss with parsley."],
    "from_my_recipe_id": None,
}


def make_client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", password="pw",
                     suggest_recipes=lambda text: [RECIPE], read_photo_items=lambda photos: [])
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    for name, category, quantity, unit in [("Spaghetti", "Dry pantry", "500", "g"),
                                           ("Garlic", "Vegetables", "2", "pieces")]:
        client.post("/items/new", data={"name": name, "category": category,
                                        "quantity": quantity, "unit": unit, "expiry_date": ""})
    client.post("/suggest", data={})  # saves the recipe as suggestion 1
    return client


def test_start_cooking_updates_the_pantry_and_shows_steps_and_shopping(tmp_path):
    client = make_client(tmp_path)

    page = client.post("/recipes/1/cook", data={
        "have_0": "on", "used_0": "200",
        "have_1": "on", "used_1": "2",
        # parsley (index 3) left unticked, so it goes on the shopping list
    }, follow_redirects=True)

    assert b"Pantry updated: 2 items changed. Used up and removed: Garlic." in page.data
    assert b"1 bunches Fresh parsley" in page.data
    assert b"Fry the garlic." in page.data

    pantry = client.get("/").data
    assert b"300 g" in pantry
    assert b"Garlic" not in pantry


def test_refreshing_the_cooking_page_does_not_change_the_pantry_again(tmp_path):
    client = make_client(tmp_path)
    client.post("/recipes/1/cook", data={"have_0": "on", "used_0": "200", "have_1": "on", "used_1": "1"})

    client.get("/recipes/1/cooking")
    client.get("/recipes/1/cooking")

    assert b"300 g" in client.get("/").data


def test_nothing_to_buy_when_everything_is_ticked(tmp_path):
    client = make_client(tmp_path)
    page = client.post("/recipes/1/cook", data={
        "have_0": "on", "used_0": "100", "have_1": "on", "used_1": "1", "have_3": "on",
    }, follow_redirects=True)
    assert b"Nothing to buy" in page.data


def test_bad_amounts_keep_your_answers_and_change_nothing(tmp_path):
    client = make_client(tmp_path)
    page = client.post("/recipes/1/cook", data={"have_0": "on", "used_0": "lots", "have_1": "on", "used_1": "1"})

    assert b"Please check the amount used for Spaghetti." in page.data
    assert b'value="lots"' in page.data
    assert b"500 g" in client.get("/").data


def test_cooking_page_before_cooking_goes_back_to_the_recipe(tmp_path):
    client = make_client(tmp_path)
    page = client.get("/recipes/1/cooking")
    assert page.status_code == 302
    assert page.headers["Location"].endswith("/recipes/1")


def test_recipe_page_warns_after_cooking(tmp_path):
    client = make_client(tmp_path)
    client.post("/recipes/1/cook", data={"have_0": "on", "used_0": "100"})
    page = client.get("/recipes/1")
    assert b"already started cooking this" in page.data
