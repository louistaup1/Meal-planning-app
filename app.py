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

import ai_client
import database
from auth import password_is_correct
from photos import MAX_PHOTOS, PhotoError, prepare_photo
from recipes import (
    CUISINES,
    DIFFICULTIES,
    PEOPLE_CHOICES,
    STYLES,
    build_request,
    check_against_pantry,
    link_to_my_recipe,
    read_filters,
    validate_my_recipe,
)
from pantry import (
    CATEGORIES,
    CATEGORY_EMOJI,
    SUGGESTED_UNITS,
    expiry_status,
    format_quantity,
    group_by_category,
    new_spice_item,
    plan_spice_additions,
    validate_item,
)

# The folder this file is in. The .env file and the database live here too.
PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))

# Read settings (like SECRET_KEY) from the .env file, if there is one.
load_dotenv(os.path.join(PROJECT_FOLDER, ".env"))

DEFAULT_DB_PATH = os.path.join(PROJECT_FOLDER, "pantry.db")


def create_app(
    db_path=DEFAULT_DB_PATH,
    password=None,
    suggest_recipes=ai_client.suggest_recipes,
    read_spices=ai_client.read_spices_from_photos,
):
    """
    Build the app. Tests pass their own `password` and pretend versions of
    `suggest_recipes` and `read_spices`, so they never call the real Claude API.
    """
    app = Flask(__name__)
    # Allow photo uploads up to 50 MB in total.
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

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
    app.jinja_env.globals["category_emoji"] = CATEGORY_EMOJI

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

    # --- Dinner suggestions -------------------------------------------------

    @app.route("/suggest", methods=["GET", "POST"])
    def suggest_page():
        filters = read_filters(request.form)
        suggestions = []
        error = None

        if request.method == "POST":
            pantry_items = database.get_all_items(app.config["DB_PATH"])
            if not pantry_items:
                error = "Your pantry is empty. Add a few ingredients first."
            else:
                try:
                    my_recipes = database.get_all_my_recipes(app.config["DB_PATH"])
                    request_text = build_request(pantry_items, filters, my_recipes=my_recipes)
                    recipes = suggest_recipes(request_text)
                except ai_client.SuggestionError as problem:
                    error = str(problem)
                else:
                    for recipe in recipes[:3]:
                        recipe = link_to_my_recipe(recipe, my_recipes)
                        suggestion_id = database.save_suggestion(app.config["DB_PATH"], recipe)
                        checked = check_against_pantry(recipe, pantry_items)
                        checked["id"] = suggestion_id
                        suggestions.append(checked)
                    if not suggestions:
                        error = "Claude didn't find a recipe this time. Try different filters."

        return render_template(
            "suggest.html",
            filters=filters,
            cuisines=CUISINES,
            difficulties=DIFFICULTIES,
            styles=STYLES,
            people_choices=PEOPLE_CHOICES,
            suggestions=suggestions,
            error=error,
        )

    @app.route("/recipes/<int:suggestion_id>")
    def recipe_page(suggestion_id):
        recipe = database.get_suggestion(app.config["DB_PATH"], suggestion_id)
        if recipe is None:
            abort(404)
        # Check against the pantry as it is right now.
        pantry_items = database.get_all_items(app.config["DB_PATH"])
        recipe = check_against_pantry(recipe, pantry_items)
        return render_template("recipe.html", recipe=recipe)

    # --- Spices from photos -----------------------------------------------

    @app.route("/spices/photos", methods=["GET", "POST"])
    def spice_photos_page():
        error = None
        if request.method == "POST":
            uploads = [f for f in request.files.getlist("photos") if f.filename]
            if not uploads:
                error = "Please choose at least one photo."
            elif len(uploads) > MAX_PHOTOS:
                error = f"Please choose up to {MAX_PHOTOS} photos at a time."
            else:
                try:
                    photos = [prepare_photo(f.read(), f.filename) for f in uploads]
                    spice_names = read_spices(photos)
                except (PhotoError, ai_client.SuggestionError) as problem:
                    error = str(problem)
                else:
                    pantry_items = database.get_all_items(app.config["DB_PATH"])
                    plan = plan_spice_additions(spice_names, pantry_items)
                    if not plan:
                        error = "Claude couldn't read any spice labels. Try a closer, brighter photo."
                    else:
                        return render_template("spice_review.html", plan=plan)
        return render_template("spice_photos.html", error=error, max_photos=MAX_PHOTOS)

    @app.route("/spices/add", methods=["POST"])
    def add_spices_action():
        pantry_items = database.get_all_items(app.config["DB_PATH"])
        plan = plan_spice_additions(request.form.getlist("spice"), pantry_items)
        added = 0
        for spice in plan:
            if not spice["already_have"]:
                database.add_item(app.config["DB_PATH"], new_spice_item(spice["name"]))
                added += 1
        flash("Added 1 spice." if added == 1 else f"Added {added} spices.")
        return redirect(url_for("pantry_page"))

    # --- My recipes --------------------------------------------------------

    @app.route("/my-recipes", methods=["GET", "POST"])
    def my_recipes_page():
        form = request.form if request.method == "POST" else {}
        errors = []
        if request.method == "POST":
            title, text, errors = validate_my_recipe(form)
            if not errors:
                database.add_my_recipe(app.config["DB_PATH"], title, text)
                flash(f"Saved {title}.")
                return redirect(url_for("my_recipes_page"))
        my_recipes = database.get_all_my_recipes(app.config["DB_PATH"])
        return render_template("my_recipes.html", my_recipes=my_recipes, form=form, errors=errors)

    @app.route("/my-recipes/<int:recipe_id>")
    def my_recipe_page(recipe_id):
        recipe = database.get_my_recipe(app.config["DB_PATH"], recipe_id)
        if recipe is None:
            abort(404)
        return render_template("my_recipe.html", recipe=recipe)

    @app.route("/my-recipes/<int:recipe_id>/delete", methods=["POST"])
    def delete_my_recipe_action(recipe_id):
        recipe = database.get_my_recipe(app.config["DB_PATH"], recipe_id)
        if recipe is None:
            abort(404)
        database.delete_my_recipe(app.config["DB_PATH"], recipe_id)
        flash(f"Deleted {recipe['title']}.")
        return redirect(url_for("my_recipes_page"))

    return app


# PythonAnywhere (and other hosts) look for a variable called "app".
app = create_app()

if __name__ == "__main__":
    # host="0.0.0.0" lets other devices on the same Wi-Fi open the app.
    app.run(host="0.0.0.0", port=5000, debug=True)
