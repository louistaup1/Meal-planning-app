"""
Deploy Pantry Chef to PythonAnywhere from Claude Code's cloud session.

What it does:
  1. Types the usual update steps into one of your PythonAnywhere Bash consoles:
     go to the project, switch on the virtualenv, git pull, install add-ons, run the tests.
  2. Waits for the result.
  3. Only if everything passed: reloads the website, then checks the login page loads.
  4. Optionally (--smoke): runs scripts/smoke_test.py on PythonAnywhere, which makes one
     real Claude request with the app's own key (costs a few cents).

The PythonAnywhere API token is never in this file. In Claude Code's cloud environment the
network proxy adds it to requests for www.pythonanywhere.com automatically.

Usage:
  python scripts/deploy.py                  # deploy
  python scripts/deploy.py --smoke recipes  # deploy, then test real suggestions
  python scripts/deploy.py --smoke all      # deploy, then test suggestions and photo reading
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request

USERNAME = "ltaup1"
DOMAIN = "ltaup1.pythonanywhere.com"
API = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}"

UPDATE_STEPS = (
    "cd ~/Meal-planning-app && workon pantry-chef && git pull && "
    "pip install -q -r requirements.txt && pytest -q"
)


class DeployError(Exception):
    """Something went wrong, with a message that explains what."""


def call_api(method, path, data=None):
    """Send one request to the PythonAnywhere API and return the answer (JSON or text)."""
    body = None
    headers = {"Authorization": "Token proxy-injected"}  # the proxy swaps in the real token
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(API + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise DeployError(f"PythonAnywhere said {error.code} for {method} {path}: {error.read()[:300]!r}")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def make_marker():
    """
    A random word to spot the end of our command in the console output.
    The command prints MARKER-OK-<exit code>. The typed command itself shows "$?", not
    a number, so we never confuse the echoed command with its result.
    """
    return f"PANTRYDEPLOY{random.randint(100000, 999999)}"


def find_result(output, marker):
    """Return the exit code printed after the command, or None if it hasn't finished yet."""
    found = re.findall(rf"{marker}-OK-(\d+)", output)
    return int(found[-1]) if found else None


def choose_console():
    """Use the most recently opened Bash console on the account."""
    consoles = [c for c in call_api("GET", "/consoles/") if c["executable"] == "bash"]
    if not consoles:
        raise DeployError(
            "There's no Bash console open on PythonAnywhere. Open one (Consoles → Bash) "
            "once in Safari, then try again."
        )
    return consoles[-1]["id"]


def run_in_console(console_id, command, wait_seconds=300):
    """Type a command into the console, wait for it to finish, return (exit code, output)."""
    marker = make_marker()
    call_api("POST", f"/consoles/{console_id}/send_input/",
             {"input": f"{command}; echo {marker}-OK-$?\n"})
    waited = 0
    output = ""
    while waited < wait_seconds:
        time.sleep(3)
        waited += 3
        answer = call_api("GET", f"/consoles/{console_id}/get_latest_output/")
        output = answer.get("output", "") if isinstance(answer, dict) else str(answer)
        code = find_result(output, marker)
        if code is not None:
            return code, output
    raise DeployError(f"The console didn't finish within {wait_seconds} seconds. Last output:\n{output[-1500:]}")


def check_site():
    """The login page should load (status 200) after a reload."""
    try:
        with urllib.request.urlopen(f"https://{DOMAIN}/login", timeout=60) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main():
    parser = argparse.ArgumentParser(description="Deploy Pantry Chef to PythonAnywhere.")
    parser.add_argument("--smoke", choices=["recipes", "photos", "all"],
                        help="after deploying, run a real Claude test on PythonAnywhere")
    args = parser.parse_args()

    console_id = choose_console()
    print(f"Using Bash console {console_id}.")

    print("Updating code, installing add-ons and running tests on PythonAnywhere...")
    code, output = run_in_console(console_id, UPDATE_STEPS)
    print(output[-1500:])
    if code != 0:
        raise DeployError("An update step or a test failed on PythonAnywhere, so the site was NOT reloaded.")

    print("Reloading the website...")
    call_api("POST", f"/webapps/{DOMAIN}/reload/")
    status = check_site()
    print(f"Login page answered with status {status}.")
    if status != 200:
        raise DeployError("The site didn't come back properly after the reload.")

    if args.smoke:
        print(f"Running the real Claude test ({args.smoke}) on PythonAnywhere...")
        code, output = run_in_console(
            console_id, f"cd ~/Meal-planning-app && python scripts/smoke_test.py {args.smoke}")
        print(output[-2500:])
        if code != 0:
            raise DeployError("The real Claude test failed (the site is deployed, though).")

    print("DEPLOY OK")


if __name__ == "__main__":
    try:
        main()
    except DeployError as problem:
        print(f"DEPLOY FAILED: {problem}")
        sys.exit(1)
