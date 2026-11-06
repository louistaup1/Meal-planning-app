"""Tests for the password lock."""

from app import create_app
from auth import password_is_correct


def make_client(tmp_path, password="secret-pass"):
    app = create_app(db_path=tmp_path / "test.db", password=password)
    app.config["TESTING"] = True
    return app.test_client()


def test_password_check():
    assert password_is_correct("secret-pass", "secret-pass")
    assert not password_is_correct("wrong", "secret-pass")
    # No password set means nobody gets in.
    assert not password_is_correct("", "")


def test_pages_are_locked_until_you_log_in(tmp_path):
    client = make_client(tmp_path)
    page = client.get("/")
    assert page.status_code == 302
    assert page.headers["Location"].endswith("/login")


def test_wrong_password_is_refused(tmp_path):
    client = make_client(tmp_path)
    page = client.post("/login", data={"password": "wrong"})
    assert b"That password isn&#39;t right." in page.data
    assert client.get("/").status_code == 302


def test_right_password_unlocks_and_logout_locks_again(tmp_path):
    client = make_client(tmp_path)
    client.post("/login", data={"password": "secret-pass"})
    assert b"My pantry" in client.get("/").data

    client.post("/logout")
    assert client.get("/").status_code == 302


def test_app_stays_locked_when_no_password_is_set(tmp_path):
    client = make_client(tmp_path, password="")
    page = client.post("/login", data={"password": ""}, follow_redirects=True)
    assert b"No password has been set yet" in page.data
    assert client.get("/").status_code == 302
