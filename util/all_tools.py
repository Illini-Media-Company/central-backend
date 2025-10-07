# This file contains helper functions for the Tools API
#
# Created by Jacob Slabosz on Oct. 1, 2025
# Last modified Oct. 1, 2025


def format_restricted_groups(groups):
    """Accepts a list of restricted groups and reformats it as a string for correct display on user-facing pages."""

    return ", ".join(groups)
