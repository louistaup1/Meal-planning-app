"""Tests for adding items from photos (receipts, shelves, spices), using a pretend Claude."""

import io

import pytest
from PIL import Image

import ai_client
from app import create_app
from pantry import plan_photo_additions, top_up_target
from photos import MAX_SIDE, PhotoError, prepare_photo


def make_photo(width=4000, height=3000, fmt="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (width, height), "orange").save(output, format=fmt)
    return output.getvalue()


def found(name, category, quantity, unit):
    return {"name": name, "category": category, "quantity": quantity, "unit": unit}


PANTRY = [
    {"id": 1, "name": "Milk", "category": "Dairy", "quantity": 1.0, "unit": "L", "expiry_date": None},
    {"id": 2, "name": "Rice", "category": "Dry pantry", "quantity": 500.0, "unit": "g", "expiry_date": None},
]


# --- photos.py ----------------------------------------------------------------

def test_big_photos_are_shrunk_to_a_jpeg():
    small = prepare_photo(make_photo(4000, 3000))
    image = Image.open(io.BytesIO(small))
    assert image.format == "JPEG"
    assert max(image.size) == MAX_SIDE


def test_files_that_are_not_photos_are_rejected():
    with pytest.raises(PhotoError, match="Couldn't read notes.txt"):
        prepare_photo(b"just some text", "notes.txt")


# --- pantry.plan_photo_additions ----------------------------------------------

def test_new_items_are_ticked():
    plan = plan_photo_additions([found("Cherry tomatoes", "Vegetables", 250, "g")], PANTRY)
    assert plan == [{"name": "Cherry tomatoes", "category": "Vegetables", "quantity": "250",
                     "unit": "g", "include": True, "note": ""}]


def test_same_name_and_unit_will_top_up():
    plan = plan_photo_additions([found("milk", "Dairy", 2, "l")], PANTRY)
    assert plan[0]["include"] is True
    assert "You have 1 L. This will be added to it." == plan[0]["note"]


def test_same_name_but_different_unit_is_left_unticked():
    plan = plan_photo_additions([found("Rice", "Dry pantry", 1, "kg")], PANTRY)
    assert plan[0]["include"] is False
    assert "Already in your pantry as 500 g" in plan[0]["note"]


def test_duplicates_are_combined_and_odd_values_fixed():
    plan = plan_photo_additions([
        found("Eggs", "Proteins", 6, "pieces"),
        found("eggs", "Proteins", 6, "Pieces"),
        found("Mystery jar", "Snacks", 0, "jars"),
        found("", "Other", 1, ""),
    ], PANTRY)
    assert [(p["name"], p["quantity"]) for p in plan] == [("Eggs", "12"), ("Mystery jar", "1")]
    assert plan[1]["category"] == "Other"


def test_top_up_target_needs_same_name_and_unit():
    assert top_up_target({"name": "MILK", "unit": "L"}, PANTRY)["id"] == 1
    assert top_up_target({"name": "Milk", "unit": "ml"}, PANTRY) is None
    assert top_up_target({"name": "Butter", "unit": "g"}, PANTRY) is None


# --- the pages ----------------------------------------------------------------

class PretendPhotoReader:
    def __init__(self, items=None, error=None):
        self.items = items or []
        self.error = error
        self.photo_counts = []

    def __call__(self, photos):
        self.photo_counts.append(len(photos))
        if self.error:
            raise ai_client.SuggestionError(self.error)
        return self.items


def make_client(tmp_path, reader):
    app = create_app(db_path=tmp_path / "test.db", password="pw",
                     suggest_recipes=lambda text: [], read_photo_items=reader)
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    return client


def upload(client, count=1):
    photos = [(io.BytesIO(make_photo(800, 600)), f"receipt{n}.png") for n in range(count)]
    return client.post("/photos", data={"photos": photos}, content_type="multipart/form-data")


def add_milk(client):
    client.post("/items/new", data={"name": "Milk", "category": "Dairy",
                                    "quantity": "1", "unit": "L", "expiry_date": ""})


def test_photos_are_read_and_offered_for_review(tmp_path):
    reader = PretendPhotoReader(items=[found("Milk", "Dairy", 2, "L"), found("Leeks", "Vegetables", 3, "pieces")])
    client = make_client(tmp_path, reader)
    add_milk(client)

    page = upload(client, count=2)

    assert reader.photo_counts == [2]
    assert b"Check the items" in page.data
    assert b'value="Leeks"' in page.data
    assert b"This will be added to it." in page.data  # milk tops up


def test_review_form_adds_new_items_and_tops_up_existing(tmp_path):
    client = make_client(tmp_path, PretendPhotoReader())
    add_milk(client)

    page = client.post("/photos/add", data={
        "count": "3",
        "include_0": "on", "name_0": "Milk", "category_0": "Dairy", "quantity_0": "2", "unit_0": "L",
        "include_1": "on", "name_1": "Leeks", "category_1": "Vegetables", "quantity_1": "3", "unit_1": "pieces",
        # item 2 is unticked, so it's ignored
        "name_2": "Crisps", "category_2": "Other", "quantity_2": "1", "unit_2": "packs",
    }, follow_redirects=True)

    assert b"Added 1 new item and topped up 1." in page.data
    assert b"3 L" in page.data          # 1 L + 2 L
    assert b"Leeks" in page.data
    assert b"Crisps" not in page.data


def test_rows_with_mistakes_are_skipped_and_reported(tmp_path):
    client = make_client(tmp_path, PretendPhotoReader())
    page = client.post("/photos/add", data={
        "count": "2",
        "include_0": "on", "name_0": "Butter", "category_0": "Dairy", "quantity_0": "lots", "unit_0": "g",
        "include_1": "on", "name_1": "Apples", "category_1": "Fruits", "quantity_1": "4", "unit_1": "pieces",
    }, follow_redirects=True)
    assert b"Added 1 new item." in page.data
    assert b"Skipped (please check the quantity): Butter." in page.data


def test_too_many_photos_are_refused_before_calling_claude(tmp_path):
    reader = PretendPhotoReader(items=[found("Cumin", "Spices", 1, "jars")])
    client = make_client(tmp_path, reader)
    page = upload(client, count=6)
    assert b"up to 5 photos" in page.data
    assert reader.photo_counts == []


def test_claude_problems_are_shown_as_friendly_messages(tmp_path):
    client = make_client(tmp_path, PretendPhotoReader(error="Couldn't reach Anthropic."))
    page = upload(client)
    assert b"Couldn&#39;t reach Anthropic." in page.data


def test_nothing_found_gives_a_tip(tmp_path):
    client = make_client(tmp_path, PretendPhotoReader(items=[]))
    page = upload(client)
    assert b"Try a closer, brighter photo" in page.data


def test_read_items_sends_photos_and_categories_to_claude(monkeypatch):
    calls = {}

    class FakeAnthropic:
        def __init__(self):
            self.beta = self
            self.messages = self

        def parse(self, **settings):
            calls.update(settings)

            class Response:
                stop_reason = "end_turn"
                parsed_output = ai_client.PhotoItems(items=[
                    ai_client.PhotoItem(name="Milk", category="Dairy", quantity=2, unit="L"),
                ])
            return Response()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(ai_client.anthropic, "Anthropic", FakeAnthropic)

    items = ai_client.read_items_from_photos([prepare_photo(make_photo(100, 100))])

    assert items == [{"name": "Milk", "category": "Dairy", "quantity": 2.0, "unit": "L"}]
    content = calls["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert "Dry pantry, Vegetables" in content[-1]["text"]
    assert calls["output_format"] is ai_client.PhotoItems


def test_claude_can_only_pick_known_categories():
    with pytest.raises(ValueError):
        ai_client.PhotoItem(name="Crisps", category="Snacks", quantity=1, unit="packs")
