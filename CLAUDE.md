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
- **Claude deploys** with `.venv/bin/python scripts/deploy.py` once changes are merged and pushed
  to `main`. It types `git pull`, `pip install` and `pytest` into the user's PythonAnywhere Bash
  console through the PythonAnywhere API, reloads the site only if the tests pass, then checks the
  login page loads. Add `--smoke recipes|photos|tidy|all` to run `scripts/smoke_test.py` on
  PythonAnywhere: real Claude requests with the app's own key (about 5–10 cents for recipes,
  2–4 cents for photos, 1–3 cents for tidying). Run the smoke test after changes that touch Claude requests.
- Deploying changes the live site, so get the user's OK in the conversation first (Claude Code's
  safety check also asks for it).
- If the deploy says no console is ready (PythonAnywhere error 412), ask the user to open their
  Bash console in Safari (PythonAnywhere → Consoles) and wait for the `$` prompt, then retry.
- The PythonAnywhere token is saved as a network secret on the **"Meal-planning-app"** cloud
  environment (the proxy adds it; it's never in code). That environment also allows
  `ltaup1.pythonanywhere.com` and has a setup script that installs `requirements.txt`.
  This cloud session can't call the Claude API directly; real-Claude checks run on PythonAnywhere.
- Manual fallback for the user, if deploying from here isn't possible (give all five lines, then
  remind them to tap **Reload** on the Web tab):
  ```
  cd ~/Meal-planning-app
  workon pantry-chef
  git pull
  pip install -r requirements.txt
  pytest
  ```
- The free PythonAnywhere site must be renewed before **7 December 2026** (Web tab →
  "Run until 3 months from today"). Remind the user as that date gets close.
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
| `database.py` | SQLite tables `pantry_items`, `my_recipes`, `my_recipe_details` (tidied recipe JSON), `suggestions` (recipe JSON), `cooked_log` |
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
  functions (`suggest_recipes`, `read_photo_items`, `tidy_recipe`), or monkeypatch
  `ai_client.anthropic.Anthropic`. `tests/conftest.py` blocks real calls as a safety net.
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

- Built: pantry (folding categories), password, Add from photos (receipts, PDFs, shelves,
  spices), My recipes (paste, tidied by Claude into ingredients and steps, or ⭐ Save; each can be
  cooked), suggestions with filters (meal, dish, cuisine, difficulty, style, people), cook flow,
  cooking diary ("Cooked before" on suggestions), app icon.
- Not built: weekly shopping lists, meal scheduling, user accounts, sharing. Only build these
  when asked, one at a time.
- Parked idea: a "What are you in the mood for?" text box above the filters, plus at most one
  clarifying question from Claude (mockups were made). Don't build it unless asked.
- This cloud environment can't reach most websites (for example recipe sites). Ask the user before
  allowing new hosts.
