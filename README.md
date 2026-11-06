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
It takes about 20 minutes.

Wherever you see `YOURNAME`, use your PythonAnywhere username.

### Part A: Create a GitHub key so PythonAnywhere can copy the code

Your code is in a *private* GitHub repository, so PythonAnywhere needs a
read-only key to download it.

1. In Safari, go to **github.com** and sign in.
2. Tap your profile picture (top right), then **Settings**.
3. Scroll to the bottom and tap **Developer settings**.
4. Tap **Personal access tokens**, then **Fine-grained tokens**, then **Generate new token**.
5. Fill in the form:
   - **Token name:** `pythonanywhere`
   - **Expiration:** 90 days. You can make a new one later.
   - **Repository access:** choose **Only select repositories**, then pick **Meal-planning-app**.
   - **Permissions → Repository permissions → Contents:** choose **Read-only**.
6. Tap **Generate token**, then copy the token. It starts with `github_pat_`.
   Paste it into the Notes app for a few minutes. GitHub will only show it once.

### Part B: Create a PythonAnywhere account

7. Go to **pythonanywhere.com**, tap **Pricing & signup**, and create a free **Beginner** account.
8. Confirm your email address.

### Part C: Copy the code and install what it needs

9. On the PythonAnywhere dashboard, tap **Consoles**, then **Bash**.
   A black window opens. This is where you type commands. Type (or paste) each line
   below, then press Return, and wait for it to finish before the next one.
10. Copy the code:
    ```
    git clone https://github.com/louistaup1/Meal-planning-app.git
    ```
    When it asks for a **Username**, type `louistaup1`.
    When it asks for a **Password**, paste the token from step 6. Nothing appears
    while you paste. That's normal.
11. Go into the project folder:
    ```
    cd Meal-planning-app
    ```
12. Create a private "box" for the app's add-ons (called a virtual environment):
    ```
    mkvirtualenv --python=/usr/bin/python3.12 pantry-chef
    ```
13. Install the add-ons:
    ```
    pip install -r requirements.txt
    ```
14. Check that everything works by running the automated tests:
    ```
    pytest
    ```
    You should see a line like `24 passed`.

### Part D: Create your private settings file (.env)

15. Still in the Bash console, make your settings file from the template:
    ```
    cp .env.example .env
    ```
16. Generate a random secret:
    ```
    python -c "import secrets; print(secrets.token_hex(32))"
    ```
    Copy the long line of letters and numbers it prints.
17. Tap the PythonAnywhere logo to go back to the dashboard. Tap **Files**,
    open the **Meal-planning-app** folder, and tap **.env** to open it.
18. Make these changes, then tap **Save**:
    - After `APP_PASSWORD=`, type the password you want to use to open the app,
      for example `APP_PASSWORD=pick-something-only-you-know`. Use something
      long that you don't use anywhere else.
    - Replace `change-me-to-something-long-and-random` with the text you copied in step 16.
    - Leave `ANTHROPIC_API_KEY=` empty for now.

The `.env` file is never uploaded to GitHub, because the `.gitignore` file tells git to skip it.

### Part E: Turn it into a website

19. Go to the dashboard, tap **Web**, then **Add a new web app**.
20. Tap **Next**, choose **Manual configuration** (*not* "Flask"), choose **Python 3.12**, and tap **Next**.
21. On the Web page, scroll to **Code** and set:
    - **Source code:** `/home/YOURNAME/Meal-planning-app`
    - **Working directory:** `/home/YOURNAME/Meal-planning-app`
22. Scroll to **Virtualenv** and set it to `/home/YOURNAME/.virtualenvs/pantry-chef`
23. Under **Code**, tap the link next to **WSGI configuration file**. Delete everything
    in that file and paste this in, replacing `YOURNAME`:
    ```python
    import sys

    project_folder = "/home/YOURNAME/Meal-planning-app"
    if project_folder not in sys.path:
        sys.path.insert(0, project_folder)

    from app import app as application
    ```
    Tap **Save**.
24. Go back to the **Web** tab and tap the big green **Reload** button.
25. Open **https://YOURNAME.pythonanywhere.com** in Safari. You should see "Welcome back".
    Type the password from step 18 and tap **Log in**. You should now see "My pantry".
    Your iPad stays logged in for 90 days.

### Part F: Make it feel like an app on your iPad

26. In Safari, with the app open, tap the **Share** button (square with an arrow), then
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
   If it asks for a username and password, use `louistaup1` and your GitHub token.
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
| `.env.example` | Template for your private settings file `.env` |

## Running on a computer instead (optional)

If you get a computer later: install Python 3.12+ and Git, then in a terminal run
`git clone https://github.com/louistaup1/Meal-planning-app.git`, `cd Meal-planning-app`,
`python -m venv .venv`, activate it (`source .venv/bin/activate` on Mac,
`.venv\Scripts\activate` on Windows), `pip install -r requirements.txt`,
`cp .env.example .env`, and `python app.py`. Then open http://localhost:5000.
