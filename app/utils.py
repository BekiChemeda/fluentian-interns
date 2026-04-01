"""
utils.py
Utility functions for the Telegram bot.
"""
import re
from typing import List

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
URL_REGEX = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    return bool(EMAIL_REGEX.match(email))


def is_valid_url(url: str) -> bool:
    """Validate URL format for submission links."""
    return bool(URL_REGEX.match(url.strip()))


def chunk_list(lst: List, n: int) -> List[List]:
    """Split list into chunks of size n."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]
