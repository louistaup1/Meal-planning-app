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
