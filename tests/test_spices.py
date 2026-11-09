"""Tests for adding spices from photos, using a pretend Claude."""

import io

import pytest
from PIL import Image

import ai_client
from app import create_app
from pantry import plan_spice_additions
from photos import MAX_SIDE, PhotoError, prepare_photo


def make_photo(width=4000, height=3000, fmt="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (width, height), "orange").save(output, format=fmt)
    return output.getvalue()


# --- photos.py ----------------------------------------------------------------

def test_big_photos_are_shrunk_to_a_jpeg():
    small = prepare_photo(make_photo(4000, 3000))
    image = Image.open(io.BytesIO(small))
    assert image.format == "JPEG"
    assert max(image.size) == MAX_SIDE


def test_files_that_are_not_photos_are_rejected():
    with pytest.raises(PhotoError, match="Couldn't read notes.txt"):
        prepare_photo(b"just some text", "notes.txt")


# --- pantry.plan_spice_additions ----------------------------------------------

def test_plan_removes_duplicates_and_marks_spices_you_have():
    pantry = [{"name": "Paprika", "category": "Spices"}]
    plan = plan_spice_additions(["paprika", "Cumin", "cumin ", "", "Turmeric"], pantry)
    assert plan == [
        {"name": "paprika", "already_have": True},
        {"name": "Cumin", "already_have": False},
        {"name": "Turmeric", "already_have": False},
    ]


# --- the pages ----------------------------------------------------------------

class PretendSpiceReader:
    def __init__(self, spices=None, error=None):
        self.spices = spices or []
        self.error = error
        self.photo_counts = []

    def __call__(self, photos):
        self.photo_counts.append(len(photos))
        if self.error:
            raise ai_client.SuggestionError(self.error)
        return self.spices


def make_client(tmp_path, reader):
    app = create_app(db_path=tmp_path / "test.db", password="pw",
                     suggest_recipes=lambda text: [], read_spices=reader)
    app.config["TESTING"] = True
    client = app.test_client()
    client.post("/login", data={"password": "pw"})
    return client


def upload(client, count=1):
    photos = [(io.BytesIO(make_photo(800, 600)), f"spices{n}.png") for n in range(count)]
    return client.post("/spices/photos", data={"photos": photos}, content_type="multipart/form-data")


def test_photos_are_read_and_offered_for_review(tmp_path):
    reader = PretendSpiceReader(spices=["Cumin", "Oregano"])
    client = make_client(tmp_path, reader)
    client.post("/items/new", data={"name": "Oregano", "category": "Spices",
                                    "quantity": "1", "unit": "jars", "expiry_date": ""})

    page = upload(client, count=2)

    assert reader.photo_counts == [2]
    assert b"Check the spices" in page.data
    assert b'value="Cumin"\n               checked' in page.data
    assert b"already in your pantry" in page.data  # Oregano


def test_ticked_spices_are_added_as_one_jar(tmp_path):
    client = make_client(tmp_path, PretendSpiceReader())
    page = client.post("/spices/add", data={"spice": ["Cumin", "Smoked paprika"]}, follow_redirects=True)
    assert b"Added 2 spices." in page.data
    assert b"Smoked paprika" in page.data
    assert b"1 jars" in page.data


def test_spices_already_in_pantry_are_not_added_twice(tmp_path):
    client = make_client(tmp_path, PretendSpiceReader())
    client.post("/spices/add", data={"spice": ["Cumin"]})
    page = client.post("/spices/add", data={"spice": ["cumin"]}, follow_redirects=True)
    assert b"Added 0 spices." in page.data


def test_too_many_photos_are_refused_before_calling_claude(tmp_path):
    reader = PretendSpiceReader(spices=["Cumin"])
    client = make_client(tmp_path, reader)
    page = upload(client, count=6)
    assert b"up to 5 photos" in page.data
    assert reader.photo_counts == []


def test_claude_problems_are_shown_as_friendly_messages(tmp_path):
    client = make_client(tmp_path, PretendSpiceReader(error="Couldn't reach Anthropic."))
    page = upload(client)
    assert b"Couldn&#39;t reach Anthropic." in page.data


def test_no_spices_found_gives_a_tip(tmp_path):
    client = make_client(tmp_path, PretendSpiceReader(spices=[]))
    page = upload(client)
    assert b"Try a closer, brighter photo" in page.data


def test_read_spices_sends_photos_to_claude(monkeypatch):
    calls = {}

    class FakeAnthropic:
        def __init__(self):
            self.beta = self
            self.messages = self

        def parse(self, **settings):
            calls.update(settings)

            class Response:
                stop_reason = "end_turn"
                parsed_output = ai_client.SpiceList(spices=["Cumin"])
            return Response()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(ai_client.anthropic, "Anthropic", FakeAnthropic)

    spices = ai_client.read_spices_from_photos([prepare_photo(make_photo(100, 100))])

    assert spices == ["Cumin"]
    content = calls["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert calls["output_format"] is ai_client.SpiceList
    assert calls["output_config"] == {"effort": "low"}
