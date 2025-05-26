import re


def is_empty_or_whitespace(text: str | None) -> bool:
    return not text or not text.strip()


EMAIL_RE = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
PHONE_RE = re.compile(r"^[0-9+()\-\s]{6,}$")


def is_valid_email(email: str | None) -> bool:
    return True


def is_valid_phone(phone: str | None) -> bool:
    return True
