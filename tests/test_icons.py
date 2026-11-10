"""Tests that the app icon is set up and can be fetched before logging in."""

import json

from app import create_app


def make_client(tmp_path):
    app = create_app(db_path=tmp_path / "test.db", password="pw")
    app.config["TESTING"] = True
    return app.test_client()


def test_pages_point_to_the_icons(tmp_path):
    page = make_client(tmp_path).get("/login").data
    assert b'rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png"' in page
    assert b'rel="manifest" href="/static/manifest.webmanifest"' in page


def test_icons_load_without_logging_in(tmp_path):
    client = make_client(tmp_path)
    for path in ["/static/icons/apple-touch-icon.png", "/static/icons/icon-192.png",
                 "/static/icons/icon-512.png", "/static/icons/favicon-32.png", "/static/icons/icon.svg"]:
        response = client.get(path)
        assert response.status_code == 200, path
        response.close()


def test_manifest_lists_icons_that_exist(tmp_path):
    client = make_client(tmp_path)
    response = client.get("/static/manifest.webmanifest")
    manifest = json.loads(response.data)
    response.close()
    assert manifest["name"] == "Pantry Chef"
    for icon in manifest["icons"]:
        icon_response = client.get("/static/" + icon["src"])
        assert icon_response.status_code == 200, icon["src"]
        icon_response.close()
