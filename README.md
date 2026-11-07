# 🍳 Pantry Chef

A personal web app that keeps track of the ingredients you have at home and
(soon) suggests what to cook for dinner.

**What works right now (milestone 1):**
- The app is protected by a password that you choose.
- Add, edit and remove pantry items.
- Each item has a name, category, quantity, unit and optional expiry date.
- Items are grouped by category: Dry pantry, Vegetables, Fruits, Spices, Dairy, Proteins, Other.
- Items that expire within 3 days are highlighted in yellow. Expired items are highlighted in red.

**Coming next:** "What should I cook tonight?" suggestions (milestone 2) and
the step-by-step cook flow (milestone 3).

---

## Put the app online with PythonAnywhere (works from an iPad)

You only need to do this once. You can do every step in Safari.
It takes about 15 minutes.

Wherever you see `YOURNAME`, use your PythonAnywhere username.

### Part A: Create a PythonAnywhere account

1. Go to **pythonanywhere.com**, tap **Pricing & signup**, and create a free **Beginner** account.
2. Confirm your email address.

### Part B: Copy the code and install what it needs

3. On the PythonAnywhere dashboard, tap **Consoles**, then **Bash**.
   A black window opens. This is where you type commands. Type (or paste) each line
   below, then press Return, and wait for it to finish before the next one.
4. Copy the code:
    ```
    git clone https://github.com/louistaup1/Meal-planning-app.git
    ```
5. Go into the project folder:
    ```
    cd Meal-planning-app
    ```
6. Create a separate "box" for the app's add-ons (called a virtual environment):
    ```
    mkvirtualenv --python=/usr/bin/python3.12 pantry-chef
    ```
7. Install the add-ons:
    ```
    pip install -r requirements.txt
    ```
8. Check that everything works by running the automated tests:
    ```
    pytest
    ```
    You should see a line like `24 passed`.

### Part C: Create your secret settings file (.env)

9. Still in the Bash console, make your settings file from the template:
    ```
    cp .env.example .env
    ```
10. Generate a random secret:
    ```
    python -c "import secrets; print(secrets.token_hex(32))"
    ```
    Copy the long line of letters and numbers it prints.
11. Tap the PythonAnywhere logo to go back to the dashboard. Tap **Files**,
    open the **Meal-planning-app** folder, and tap **.env** to open it.
12. Make these changes, then tap **Save**:
    - After `APP_PASSWORD=`, type the password you want to use to open the app,
      for example `APP_PASSWORD=pick-something-only-you-know`. Use something
      long that you don't use anywhere else.
    - Replace `change-me-to-something-long-and-random` with the text you copied in step 10.
    - Leave `ANTHROPIC_API_KEY=` empty for now.

The `.env` file is never uploaded to GitHub, because the `.gitignore` file tells git to skip it.

### Part D: Turn it into a website

13. Go to the dashboard, tap **Web**, then **Add a new web app**.
14. Tap **Next**, choose **Manual configuration** (*not* "Flask"), choose **Python 3.12**, and tap **Next**.
15. On the Web page, scroll to **Code** and set:
    - **Source code:** `/home/YOURNAME/Meal-planning-app`
    - **Working directory:** `/home/YOURNAME/Meal-planning-app`
16. Scroll to **Virtualenv** and set it to `/home/YOURNAME/.virtualenvs/pantry-chef`
17. Under **Code**, tap the link next to **WSGI configuration file**. Delete everything
    in that file and paste this in, replacing `YOURNAME`:
    ```python
    import sys

    project_folder = "/home/YOURNAME/Meal-planning-app"
    if project_folder not in sys.path:
        sys.path.insert(0, project_folder)

    from app import app as application
    ```
    Tap **Save**.
18. Go back to the **Web** tab and tap the big green **Reload** button.
19. Open **https://YOURNAME.pythonanywhere.com** in Safari. You should see "Welcome back".
    Type the password from step 12 and tap **Log in**. You should now see "My pantry".
    Your iPad stays logged in for 90 days.

### Part E: Make it feel like an app on your iPad

20. In Safari, with the app open, tap the **Share** button (square with an arrow), then
    **Add to Home Screen**, then **Add**. Pantry Chef now has its own icon.

### Keeping it running (free account)

About every 3 months, PythonAnywhere emails you to ask you to keep the free site running.
Go to the **Web** tab and tap **Run until 3 months from today**.

### Changing your password later

Edit `APP_PASSWORD` in the `.env` file (**Files → Meal-planning-app → .env**), save it,
then tap **Reload** on the **Web** tab.

---

## Getting new versions of the app

When a new version of the code is ready:

1. On PythonAnywhere, open **Consoles → Bash** and run:
   ```
   cd ~/Meal-planning-app
   workon pantry-chef
   git pull
   pip install -r requirements.txt
   pytest
   ```
2. Go to the **Web** tab and tap **Reload**.

Your pantry data is in `pantry.db`. Updates never overwrite it.

---

## How the code is organized

| File | What it does |
|---|---|
| `app.py` | The web pages and what happens when you tap buttons |
| `auth.py` | Checks the app password |
| `pantry.py` | Pantry rules: categories, checking the form, "expiring soon" |
| `database.py` | Saving and loading items in the `pantry.db` file |
| `templates/` | The HTML pages |
| `static/style.css` | Colors, sizes and layout |
| `tests/` | Automated tests. Run them with `pytest` |
| `.env.example` | Template for your secret settings file `.env` |

## Running on a computer instead (optional)

If you get a computer later: install Python 3.12+ and Git, then in a terminal run
`git clone https://github.com/louistaup1/Meal-planning-app.git`, `cd Meal-planning-app`,
`python -m venv .venv`, activate it (`source .venv/bin/activate` on Mac,
`.venv\Scripts\activate` on Windows), `pip install -r requirements.txt`,
`cp .env.example .env`, and `python app.py`. Then open http://localhost:5000.
