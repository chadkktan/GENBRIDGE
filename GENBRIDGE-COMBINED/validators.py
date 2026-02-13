"""
All input validation + parsing:
- Email rules
- Phone rules
- Allowed avatar extensions
- Parsing interests from request data
"""

import re
from flask import Request

from config import ALLOWED_EXTENSIONS


# True if filename has an allowed image extension.
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# .com-only validator used for the Create Account UI.
# Matches message style of xxxx@xxxx.com
def validate_email_com(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.com$", (email or "").strip(), re.I))


# General email validator (NOT only .com)
# Used for login/profile flows where normal emails should work.
def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email.strip(), re.I))


# Allow +, spaces, hyphens, parentheses. Must be 8–15 digits total.
def validate_phone(phone: str) -> bool:
    v = phone.strip()
    digits_only = re.sub(r"\D", "", v)

    if len(digits_only) < 8 or len(digits_only) > 15:
        return False

    return bool(re.match(r"^[0-9+\-\s()]+$", v))


def get_interests_from_request(req: Request) -> list[str]:
    """
    Supports your current HTML logic:
    1) Checkbox list: name="interests" (multiple)
    2) Hidden input/text input: name="interests" (comma-separated)
    """
    values = req.form.getlist("interests")

    # A) multiple checkbox values
    if len(values) > 1:
        return [v.strip() for v in values if v.strip()]

    # B) one value (could be "Cooking, Travel, Music")
    if len(values) == 1:
        raw = (values[0] or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    # C) nothing received in list-form, try standard field
    raw = (req.form.get("interests", "") or "").strip()
    if not raw:
        return []

    return [x.strip() for x in raw.split(",") if x.strip()]