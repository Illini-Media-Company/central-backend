# This file contains helper functions for the Tools API
#
# Created by Jacob Slabosz on Oct. 1, 2025
# Last modified Feb. 16, 2026


def format_restricted_groups(groups: str | list[str]) -> str:
    """Accepts a list of restricted groups and reformats it as a string for correct display on user-facing pages."""

    if not groups:
        return ""

    if isinstance(groups, str):
        return groups.strip()

    if isinstance(groups, list):
        return ", ".join(groups)

    return str(groups)
