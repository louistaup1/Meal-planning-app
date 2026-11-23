"""Tests for the helper scripts (they never contact PythonAnywhere or Claude here)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import deploy  # noqa: E402
import smoke_test  # noqa: E402


def test_marker_result_ignores_the_typed_command():
    marker = "PANTRYDEPLOY123456"
    typed = f"$ pytest -q; echo {marker}-OK-$?\n"
    assert deploy.find_result(typed, marker) is None
    assert deploy.find_result(typed + "97 passed\n" + f"{marker}-OK-0\n", marker) == 0
    assert deploy.find_result(typed + "1 failed\n" + f"{marker}-OK-1\n", marker) == 1


def test_markers_are_a_fixed_word_plus_six_digits():
    marker = deploy.make_marker()
    assert marker.startswith("PANTRYDEPLOY")
    assert len(marker) == len("PANTRYDEPLOY") + 6 and marker[-6:].isdigit()


def test_update_steps_include_pip_install_and_tests():
    assert "git pull" in deploy.UPDATE_STEPS
    assert "pip install -q -r requirements.txt" in deploy.UPDATE_STEPS
    assert deploy.UPDATE_STEPS.endswith("pytest -q")


def test_smoke_recipe_check_spots_bad_answers(monkeypatch):
    useless = {"title": "Air soup", "summary": "", "cuisine": "Any", "difficulty": "Easy",
               "dish_type": "Main", "style": "Any", "total_minutes": 5, "servings": 2,
               "ingredients": [{"name": "Air", "amount": 1, "unit": "", "pantry_item_id": None,
                                "is_staple": False}],
               "steps": [], "from_my_recipe_id": None}
    monkeypatch.setattr(smoke_test.ai_client, "suggest_recipes", lambda text: [useless])
    problems = smoke_test.check_recipes()
    assert "Air soup has no steps" in problems
    assert "Air soup uses nothing from the pantry" in problems


def test_smoke_photo_check_spots_non_food(monkeypatch):
    found = [{"name": "Milk", "category": "Dairy", "quantity": 2, "unit": "L"},
             {"name": "Washing-up liquid", "category": "Other", "quantity": 1, "unit": "pieces"}]
    monkeypatch.setattr(smoke_test.ai_client, "read_items_from_photos", lambda uploads: found)
    problems = smoke_test.check_photos()
    assert "bananas weren't found on the receipt" in problems
    assert "washing-up liquid should have been skipped" in problems


def test_smoke_tidy_check_spots_untidy_answers(monkeypatch):
    untidy = {"servings": 4, "steps": ["Do everything."], "ingredients": [
        {"name": "1 red pepper, cut into chunks", "amount": 1, "unit": "", "note": "", "is_staple": False},
        {"name": "Salt and pepper", "amount": 1, "unit": "", "note": "", "is_staple": True},
    ]}
    monkeypatch.setattr(smoke_test.ai_client, "tidy_recipe", lambda title, text: untidy)
    problems = smoke_test.check_tidy()
    assert "'1 red pepper, cut into chunks' should become 'Red pepper'" in problems
    assert "'salt and pepper' should be split into two ingredients" in problems
    assert "servings should be 2, got 4" in problems
    assert "the method should be split into steps" in problems


def test_smoke_recipe_check_spots_ignored_dislikes(monkeypatch):
    sent = []
    spicy = {"title": "Spaghetti aglio, olio e peperoncino", "summary": "", "cuisine": "Italian",
             "difficulty": "Easy", "dish_type": "Main", "style": "Quick", "total_minutes": 15, "servings": 2,
             "ingredients": [{"name": "Spaghetti", "amount": 200, "unit": "g", "pantry_item_id": 1,
                              "is_staple": False},
                             {"name": "Chilli flakes", "amount": 1, "unit": "tsp", "pantry_item_id": None,
                              "is_staple": False}],
             "steps": ["Cook."], "from_my_recipe_id": None}

    def pretend(text):
        sent.append(text)
        return [spicy]

    monkeypatch.setattr(smoke_test.ai_client, "suggest_recipes", pretend)
    problems = smoke_test.check_recipes()
    assert "too spicy" in sent[0]
    assert "a big batch for 6 people" in sent[0]
    assert "Spaghetti aglio, olio e peperoncino serves 2, but the wishes asked for 6" in problems
    assert "Spaghetti aglio, olio e peperoncino was disliked and shouldn't be suggested again" in problems
    assert "Spaghetti aglio, olio e peperoncino uses chilli, but the dislike said 'too spicy'" in problems
