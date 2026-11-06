"""
The Pantry Chef web app.

Each function marked with @app.route is one page or one button action.
To start the app on your own computer: python app.py
"""

import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

import database
from auth import password_is_correct
from pantry import (
    CATEGORIES,
    SUGGESTED_UNITS,
    expiry_status,
    format_quantity,
    group_by_category,
    validate_item,
)

# The folder this file is in. The .env file and the database live here too.
PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))

# Read settings (like SECRET_KEY) from the .env file, if there is one.
load_dotenv(os.path.join(PROJECT_FOLDER, ".env"))

DEFAULT_DB_PATH = os.path.join(PROJECT_FOLDER, "pantry.db")


def create_app(db_path=DEFAULT_DB_PATH, password=None):
    app = Flask(__name__)

    # SECRET_KEY signs the "you are logged in" cookie. If it's missing from .env,
    # we make up a random one, which is safe but logs you out whenever the app restarts.
    secret_key = os.environ.get("SECRET_KEY", "")
    if secret_key in ("", "change-me-to-something-long-and-random"):
        secret_key = secrets.token_hex(32)
    app.config["SECRET_KEY"] = secret_key
    app.config["DB_PATH"] = db_path

    # The app password comes from .env (APP_PASSWORD). Tests pass their own.
    if password is None:
        password = os.environ.get("APP_PASSWORD", "")
    app.config["APP_PASSWORD"] = password

    # Stay logged in on this device for 90 days.
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=90)

    database.init_db(db_path)

    # Make these helpers usable inside the HTML templates.
    app.jinja_env.globals["expiry_status"] = expiry_status
    app.jinja_env.globals["format_quantity"] = format_quantity

    # --- Password lock -----------------------------------------------------

    @app.before_request
    def require_login():
        """Runs before every page. Sends you to the login page if needed."""
        pages_open_to_everyone = ("login_page", "static")
        if request.endpoint in pages_open_to_everyone:
            return None
        if session.get("logged_in"):
            return None
        return redirect(url_for("login_page"))

    @app.route("/login", methods=["GET", "POST"])
    def login_page():
        password_missing = app.config["APP_PASSWORD"] == ""
        error = None

        if request.method == "POST" and not password_missing:
            entered = request.form.get("password", "")
            if password_is_correct(entered, app.config["APP_PASSWORD"]):
                session.clear()
                session["logged_in"] = True
                session.permanent = True  # remember this device
                return redirect(url_for("pantry_page"))
            error = "That password isn't right."

        return render_template("login.html", error=error, password_missing=password_missing)

    @app.route("/logout", methods=["POST"])
    def logout_action():
        session.clear()
        return redirect(url_for("login_page"))

    # --- Pantry pages ------------------------------------------------------

    @app.route("/")
    def pantry_page():
        items = database.get_all_items(app.config["DB_PATH"])
        groups = group_by_category(items)
        return render_template("pantry.html", groups=groups)

    @app.route("/items/new", methods=["GET", "POST"])
    def add_item_page():
        form = request.form if request.method == "POST" else {}
        errors = []

        if request.method == "POST":
            item, errors = validate_item(form)
            if not errors:
                database.add_item(app.config["DB_PATH"], item)
                flash(f"Added {item['name']}.")
                return redirect(url_for("pantry_page"))

        return render_template(
            "item_form.html",
            title="Add an item",
            form=form,
            errors=errors,
            categories=CATEGORIES,
            units=SUGGESTED_UNITS,
        )

    @app.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
    def edit_item_page(item_id):
        existing = database.get_item(app.config["DB_PATH"], item_id)
        if existing is None:
            abort(404)

        errors = []
        if request.method == "POST":
            form = request.form
            item, errors = validate_item(form)
            if not errors:
                database.update_item(app.config["DB_PATH"], item_id, item)
                flash(f"Saved {item['name']}.")
                return redirect(url_for("pantry_page"))
        else:
            # Fill the form with the item's current values.
            form = {
                "name": existing["name"],
                "category": existing["category"],
                "quantity": format_quantity(existing["quantity"]),
                "unit": existing["unit"],
                "expiry_date": existing["expiry_date"].isoformat() if existing["expiry_date"] else "",
            }

        return render_template(
            "item_form.html",
            title=f"Edit {existing['name']}",
            form=form,
            errors=errors,
            categories=CATEGORIES,
            units=SUGGESTED_UNITS,
            item_id=item_id,
        )

    @app.route("/items/<int:item_id>/delete", methods=["POST"])
    def delete_item_action(item_id):
        existing = database.get_item(app.config["DB_PATH"], item_id)
        if existing is None:
            abort(404)
        database.delete_item(app.config["DB_PATH"], item_id)
        flash(f"Removed {existing['name']}.")
        return redirect(url_for("pantry_page"))

    return app


# PythonAnywhere (and other hosts) look for a variable called "app".
app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0" lets other devices on the same Wi-Fi open the app.
    app.run(host="0.0.0.0", port=5000, debug=True)
