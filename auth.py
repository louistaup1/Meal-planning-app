"""
Password check for the whole app.

There is one password, set as APP_PASSWORD in your private .env file.
"""

import hmac


def password_is_correct(entered, real_password):
    """
    Compare the typed password with the real one.

    Returns False if no real password has been set, so the app stays locked
    rather than open to everyone. `hmac.compare_digest` compares in a way
    that doesn't leak hints about how much of the password was right.
    """
    if not real_password:
        return False
    return hmac.compare_digest(entered.encode("utf-8"), real_password.encode("utf-8"))
