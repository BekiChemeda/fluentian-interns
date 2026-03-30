"""
utils.py
Utility functions for the Telegram bot.
"""
import re
from typing import List

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    return bool(EMAIL_REGEX.match(email))


def chunk_list(lst: List, n: int) -> List[List]:
    """Split list into chunks of size n."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]
