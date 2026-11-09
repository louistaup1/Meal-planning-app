# 🍳 Pantry Chef

A personal web app that keeps track of the ingredients you have at home and
suggests what to cook for dinner, using Claude (Anthropic's AI).

**What works right now:**
- The app is protected by a password that you choose.
- Add, edit and remove pantry items.
- Each item has a name, category, quantity, unit and optional expiry date.
- Items are grouped by category: Dry pantry, Vegetables, Fruits, Spices, Dairy, Proteins, Other.
- Items that expire within 3 days get a yellow **USE ME!** sticker. Expired items get a red **UH-OH**.
- **Add from photos:** take or choose up to 5 photos or PDFs: a paper receipt, an email
  receipt saved as a PDF, a fridge or cupboard shelf, or spice jars. Claude lists the food it can see (name, category, quantity, unit).
  You check and fix the list before anything is added. Items you already have, with the
  same unit, are topped up instead of duplicated.
- **My recipes:** paste your own recipes (any layout). Claude considers them alongside new
  ideas when suggesting dinner, and marks them "From my recipes".
- **What should I cook tonight?** suggests up to 3 recipes from your pantry. You can filter
  by cuisine, difficulty, style (quick, comfort, healthy) and number of people (1–8). Each suggestion shows the total
  time, the difficulty and what you're missing. **Back to suggestions** shows your last
  suggestions again for free (no new request to Claude).
- **Cook flow:** tap **Cook this**, then tick what you have and check the amounts used.
  **Start cooking** updates your pantry (items that are used up are removed), then shows
  the steps to tick off and a **To buy** list of anything you didn't have.

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
    You should see a line like `86 passed`.

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
    - Leave `ANTHROPIC_API_KEY=` empty for now. You'll add it in Part F.

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

### Part F: Connect Claude for dinner suggestions

The suggestions and "Add from photos" use Claude, Anthropic's AI. This is pay-as-you-go:
each tap on **Suggest** costs roughly 5–10 US cents (about 1 cent more for every 10 saved
recipes), and reading photos costs about 2–4 cents per photo or PDF page.

1. In Safari, go to **console.anthropic.com** and create an account.
2. Open **Settings → Billing** and add credit. $5 is plenty to start.
3. Open **Settings → API Keys**, tap **Create Key**, name it `pantry-chef`, and copy the key.
   It starts with `sk-ant-`. Anthropic only shows it once.
4. On PythonAnywhere, open **Files → Meal-planning-app → .env**.
5. Paste the key right after `ANTHROPIC_API_KEY=` (no spaces, no quotes), then tap **Save**.
6. Go to the **Web** tab and tap **Reload**.
7. Open the app, tap **What should I cook tonight?**, then tap **Suggest**. After up to a
   minute you should see up to 3 recipes.

Keep the key secret. Don't paste it into chats, emails or GitHub. If it ever leaks,
delete it in the Anthropic console (**Settings → API Keys**) and create a new one.

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
| `cooking.py` | Cook-flow rules: the "What did you use?" checklist, pantry updates, to-buy list |
| `recipes.py` | Recipe rules: filters, the request sent to Claude, finding missing ingredients |
| `ai_client.py` | The only file that talks to Claude. The model name is set at the top |
| `photos.py` | Shrinks photos before they're sent to Claude |
| `database.py` | Saving pantry items, your recipes and suggestions in the `pantry.db` file |
| `templates/` | The HTML pages |
| `static/style.css` | Colors, sizes and layout |
| `tests/` | Automated tests. Run them with `pytest`. They never call Claude, so they're free |
| `.env.example` | Template for your secret settings file `.env` |

## Running on a computer instead (optional)

If you get a computer later: install Python 3.12+ and Git, then in a terminal run
`git clone https://github.com/louistaup1/Meal-planning-app.git`, `cd Meal-planning-app`,
`python -m venv .venv`, activate it (`source .venv/bin/activate` on Mac,
`.venv\Scripts\activate` on Windows), `pip install -r requirements.txt`,
`cp .env.example .env`, and `python app.py`. Then open http://localhost:5000.
