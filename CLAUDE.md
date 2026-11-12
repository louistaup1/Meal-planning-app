# Pantry Chef: notes for Claude

Pantry Chef is a personal web app: a pantry list, plus Claude-powered "What should I cook?"
suggestions and a cook flow that updates the pantry. It's an MVP that works and is in daily use.

## The person you're working with

- No coding experience. Explain things in plain English, without jargon.
- Uses **only an iPad** (Safari). No computer, so nothing can be run locally on their side.
- Before each change, say in about two sentences what you're about to do and why.
- Check with them before big decisions: new features, design direction, anything that costs
  money or changes how they use the app. Small implementation choices: pick a sensible default
  and mention it.
- When a step is done, give a short summary: **what works, how they can check it, what's next**.
- Mention what any feature costs to run when it calls Claude (they pay for API credit).
- For design choices, show options as screenshots (iPad size) before building.

## Where it runs

- Hosted on **PythonAnywhere** (free account): username `ltaup1`, site `https://ltaup1.pythonanywhere.com`,
  code in `~/Meal-planning-app`, virtualenv `pantry-chef`. The free plan *can* reach `api.anthropic.com`.
- The GitHub repository is **public**. Never commit secrets.
- Deploying is currently manual, done by the user in a PythonAnywhere Bash console. Always give
  all five lines, even when nothing new needs installing, and remind them to tap **Reload** on the
  Web tab afterwards:
  ```
  cd ~/Meal-planning-app
  workon pantry-chef
  git pull
  pip install -r requirements.txt
  pytest
  ```
  A new console starts in `~` without the virtualenv, so `cd` and `workon` matter.
- Their pantry data lives in `pantry.db` on PythonAnywhere. Changes must never lose it.

## Stack and layout

Python 3.12, Flask, SQLite, Jinja templates, plain CSS, pytest. No front-end framework or build step.

| File | Job |
|---|---|
| `app.py` | Routes only. `create_app(db_path, password, suggest_recipes, read_photo_items)`; tests pass pretend functions |
| `pantry.py` | Pantry rules: categories and emojis, form validation, expiry status, photo-import planning |
| `recipes.py` | Suggestion rules: filters, the request text sent to Claude, pantry check, saving to My recipes |
| `cooking.py` | Cook flow: "What did you use?" checklist, pantry changes, to-buy list |
| `ai_client.py` | **The only file that calls Claude.** Model set in `MODEL` (Opus, the user's choice) |
| `photos.py` | Shrinks photos (1568 px JPEG) and passes PDFs through for Claude |
| `database.py` | SQLite tables `pantry_items`, `my_recipes`, `suggestions` (recipe stored as JSON) |
| `auth.py` | Single app password from `.env` |
| `templates/`, `static/style.css` | Pages and the "Candy Pop" sticker-book design |
| `tests/` | pytest, one file per area |

Keep logic in the plain-Python modules and keep routes thin, so the logic is easy to test.

## Commands

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # first time in a session
.venv/bin/pytest -q                                                 # all tests, must pass before every commit
```

To check pages visually, run the app with a pretend Claude (see the `PretendClaude` helpers in
`tests/`) and take Playwright screenshots with the `iPad Mini` device, plus `iPhone 13` for layout checks.

## Rules for code

- Simple, readable code with plain-English comments. Avoid clever shortcuts.
- Every change gets tests. **Tests never call the real Claude API**: use the injected pretend
  functions, or monkeypatch `ai_client.anthropic.Anthropic`.
- Claude calls use `client.beta.messages.parse` with a Pydantic `output_format`, the
  `server-side-fallback-2026-07-01` beta and `fallbacks="default"`. All errors become a
  friendly `SuggestionError` message. Read the claude-api skill before changing this file.
- Database: tables are created with `CREATE TABLE IF NOT EXISTS` and there are no migrations.
  Don't change existing columns. Put new per-suggestion data inside `recipe_json`, and make
  templates cope with older rows that lack the new field.
- Design: colours are named variables at the top of `static/style.css`. Keep the Candy Pop look:
  thick black outlines, hard shadows, Fredoka for headings and Nunito for text.
- Template tests: Jinja escapes apostrophes (`isn't` becomes `isn&#39;t`), and flash messages
  appear on the next page, which can make "not in page" checks pass or fail unexpectedly.

## Secrets

`.env` (ignored by git) holds `ANTHROPIC_API_KEY`, `APP_PASSWORD` and `SECRET_KEY`; `.env.example`
is the template. Before each commit, check the diff has no keys (`sk-ant-...`). Never ask the user
to paste a key into the chat.

## Git

- One branch per change. Commit after each working step with a short message.
- When the tests pass, fast-forward merge into `main` and push. The user has agreed to this.
- Update `README.md` when features or the expected test count change. Its numbered steps are
  written for an iPad user.

## Scope

- Built: pantry, password, Add from photos (receipts, PDFs, shelves, spices), My recipes
  (paste or ⭐ Save), suggestions with filters (meal, dish, cuisine, difficulty, style, people),
  cook flow, app icon.
- Not built: weekly shopping lists, meal scheduling, user accounts, sharing. Only build these
  when asked, one at a time.
- Parked idea: a "What are you in the mood for?" text box above the filters, plus at most one
  clarifying question from Claude (mockups were made). Don't build it unless asked.
- This cloud environment can't reach most websites (for example recipe sites) and has no
  PythonAnywhere access.
