"""Tests for 👍 / 👎 ratings and how they guide suggestions."""

from recipes import (
    MAX_RATINGS_SHARED,
    build_request,
    describe_ratings,
    disliked_my_recipe_ids,
    find_rating,
    rating_key,
    read_filters,
)


def rating(title, value, note="", key=None, my_recipe_id=None):
    from recipes import title_key
    return {"title_key": key or title_key(title), "title": title, "rating": value,
            "note": note, "my_recipe_id": my_recipe_id, "rated_at": "2026-11-17T19:00:00"}


RATINGS = [  # newest first, as the database returns them
    rating("Spicy chicken curry", -1, "too spicy"),
    rating("Lemon risotto", 1, "lovely and fresh"),
    rating("Grandma's lasagne", 1, key="my:3", my_recipe_id=3),
    rating("Mushroom stroganoff", -1, key="my:4", my_recipe_id=4),
]


def test_rating_keys():
    assert rating_key({"title": "Lemon Risotto!"}) == "lemon risotto"
    assert rating_key({"title": "Anything", "from_my_recipe_id": 3}) == "my:3"
    assert rating_key({"title": "Anything", "saved_as_my_recipe_id": 5}) == "my:5"


def test_find_rating_by_my_recipe_or_title():
    assert find_rating({"title": "Nonna's lasagne", "from_my_recipe_id": 3}, RATINGS)["rating"] == 1
    assert find_rating({"title": "spicy chicken curry"}, RATINGS)["note"] == "too spicy"
    assert find_rating({"title": "Something new"}, RATINGS) is None


def test_rating_given_before_saving_is_still_found_after():
    # Rated as a Claude idea (by title), then saved with ⭐ as My recipe 9.
    assert find_rating({"title": "Lemon risotto", "saved_as_my_recipe_id": 9}, RATINGS)["rating"] == 1


def test_describe_ratings_lists_likes_and_dislikes_with_reasons():
    text = describe_ratings(RATINGS)
    assert "Recipes I liked:\n- Lemon risotto (why: lovely and fresh)\n- Grandma's lasagne" in text
    assert "Recipes I disliked:\n- Spicy chicken curry (why: too spicy)\n- Mushroom stroganoff" in text
    assert describe_ratings([]) == ""


def test_only_the_most_recent_ratings_are_shared():
    many = [rating(f"Dish {n}", 1) for n in range(MAX_RATINGS_SHARED + 5)]
    shared = [line for line in describe_ratings(many).splitlines() if line.startswith("- Dish")]
    assert len(shared) == MAX_RATINGS_SHARED
    assert shared[0] == "- Dish 0"     # the newest one comes first


def test_ratings_are_added_to_the_request():
    pantry = [{"id": 1, "name": "Rice", "category": "Dry pantry", "quantity": 1.0, "unit": "kg", "expiry_date": None}]
    text = build_request(pantry, read_filters({}), ratings=RATINGS)
    assert text.endswith("- Mushroom stroganoff")
    assert "Recipes I disliked:" in text
    assert "Recipes I liked" not in build_request(pantry, read_filters({}))


def test_disliked_my_recipes_are_left_out():
    assert disliked_my_recipe_ids(RATINGS) == {4}


# --- What a tap does ------------------------------------------------------------

from recipes import rating_change  # noqa: E402


def test_rating_change():
    liked = {"rating": 1, "note": "yum"}
    assert rating_change(None, "like") == ("save", 1, "")
    assert rating_change(liked, "like") == ("delete",)                      # tap again to undo
    assert rating_change(liked, "dislike") == ("save", -1, "")              # switching starts afresh
    assert rating_change(liked, "note", "  kids loved it ") == ("save", 1, "kids loved it")
    assert rating_change(None, "note", "orphan") == ("nothing",)
    assert rating_change(liked, "nonsense") == ("nothing",)
    assert rating_change(liked, "note", "x" * 500)[2] == "x" * 200


# --- The pages ----------------------------------------------------------------

import ai_client  # noqa: E402
from app import create_app  # noqa: E402


def tidy_fails(title, text):
    raise ai_client.SuggestionError("Pretend: not tidied.")

SUGGESTION = {
    "title": "Spicy chicken curry", "summary": "Hot!", "cuisine": "Indian", "difficulty": "Easy",
    "dish_type": "Main", "style": "Comfort", "total_minutes": 40, "servings": 2,
    "ingredients": [{"name": "Rice", "amount": 150, "unit": "g", "pantry_item_id": 1, "is_staple": False}],
    "steps": ["Cook it."], "from_my_recipe_id": None,
}


class PretendSuggest:
    def __init__(self, recipes=None):
        self.recipes = recipes if recipes is not None else [SUGGESTION]
        self.requests = []

    def __call__(self, request_text):
        self.requests.append(request_text)
        return self.recipes


def make_client(tmp_path, suggest=None):
    app = create_app(db_path=tmp_path / "test.db", password="pw", suggest_recipes=suggest or PretendSuggest(),
                     read_photo_items=lambda photos: [], tidy_recipe=tidy_fails)
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    client.post("/items/new", data={"name": "Rice", "category": "Dry pantry",
                                    "quantity": "1", "unit": "kg", "expiry_date": ""})
    return client


def test_like_from_a_card_and_tap_again_to_undo(tmp_path):
    client = make_client(tmp_path)
    client.post("/suggest", data={})

    page = client.post("/recipes/1/rate", data={"choice": "like", "back": "suggest"}, follow_redirects=True)
    assert b'class="rate-button is-on"' in page.data
    assert b"What should I cook?" in page.data              # back on the suggestions page
    assert b'name="note"' in page.data                      # the "Why?" box appears

    page = client.post("/recipes/1/rate", data={"choice": "like", "back": "suggest"}, follow_redirects=True)
    assert b"is-on" not in page.data
    assert b'name="note"' not in page.data


def test_dislike_with_a_reason_guides_the_next_suggestion(tmp_path):
    suggest = PretendSuggest()
    client = make_client(tmp_path, suggest)
    client.post("/suggest", data={})
    client.post("/recipes/1/rate", data={"choice": "dislike", "back": "recipe"})
    client.post("/recipes/1/rate", data={"choice": "note", "note": "too spicy", "back": "recipe"})

    client.post("/suggest", data={})

    assert "Recipes I disliked:\n- Spicy chicken curry (why: too spicy)" in suggest.requests[-1]


def test_rating_from_the_cooking_page(tmp_path):
    client = make_client(tmp_path)
    client.post("/suggest", data={})
    client.post("/recipes/1/cook", data={"have_0": "on", "used_0": "150"})

    page = client.get("/recipes/1/cooking")
    assert b"How was it?" in page.data

    page = client.post("/recipes/1/rate", data={"choice": "like", "back": "cooking"}, follow_redirects=True)
    assert b"How was it?" in page.data
    assert b'class="rate-button is-on"' in page.data


def test_disliked_my_recipes_are_no_longer_offered_to_claude(tmp_path):
    suggest = PretendSuggest(recipes=[])
    client = make_client(tmp_path, suggest)
    client.post("/my-recipes", data={"title": "Mushroom stroganoff", "text": "Mushrooms, cream."})

    client.post("/suggest", data={})
    assert "Mushroom stroganoff" in suggest.requests[-1]

    page = client.post("/my-recipes/1/rate", data={"choice": "dislike"}, follow_redirects=True)
    assert b"is-dislike" in page.data
    client.post("/suggest", data={})
    assert "My saved recipes" not in suggest.requests[-1]
    assert "Recipes I disliked:\n- Mushroom stroganoff" in suggest.requests[-1]
    assert "Mushroom stroganoff 👎".encode() in client.get("/my-recipes").data


def test_a_rating_given_before_saving_is_kept_once(tmp_path):
    suggest = PretendSuggest()
    client = make_client(tmp_path, suggest)
    client.post("/suggest", data={})
    client.post("/recipes/1/rate", data={"choice": "like", "back": "recipe"})
    client.post("/recipes/1/save", data={"back": "recipe"})            # now My recipe 1

    page = client.get("/my-recipes/1")
    assert b'class="rate-button is-on"' in page.data                 # still shows 👍

    client.post("/my-recipes/1/rate", data={"choice": "note", "note": "a keeper"})
    client.post("/suggest", data={})
    liked_lines = [line for line in suggest.requests[-1].splitlines()
                   if line.startswith("- ") and "Spicy chicken curry" in line]
    assert liked_lines == ["- Spicy chicken curry (why: a keeper)"]
