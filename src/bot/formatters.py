"""Text formatting helpers for user-facing messages.

Centralizes repeated formatting patterns to avoid duplication
across handler modules.
"""
from typing import Optional


def format_year_suffix(year: Optional[int]) -> str:
    """Return ' (YEAR)' if year is set, otherwise empty string.

    Example: format_year_suffix(2024) -> ' (2024)'
    """
    return f" ({year})" if year else ""


def format_user_display_name(
    username: Optional[str],
    first_name: Optional[str] = None,
    fallback: str = "Аноним",
) -> str:
    """Format a user's display name for messages.

    Priority: @username > first_name > fallback

    Example: format_user_display_name("john") -> '@john'
    """
    if username:
        return f"@{username}"
    return first_name or fallback


def format_movie_title(title: str, year: Optional[int] = None) -> str:
    """Format movie title with optional year.

    Example: format_movie_title("Matrix", 1999) -> 'Matrix (1999)'
    """
    return f"{title}{format_year_suffix(year)}"
