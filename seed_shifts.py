"""
seed_shifts.py
Run once to populate dummy shift data for testing.
Call seed_dummy_shifts() from a Flask route or shell.
"""

from datetime import date, timedelta
from google.cloud import ndb
from db import client as dbclient
from util.shift_utils import get_week_bounds, assign_shift, SHIFT_START_HOURS


# Dummy editors (use real emails if they exist in your system,
# or fake ones for local testing)
DUMMY_EDITORS = [
    {"email": "alice@illinimedia.com", "name": "Alice Johnson"},
    {"email": "bob@illinimedia.com", "name": "Bob Smith"},
    {"email": "carol@illinimedia.com", "name": "Carol Davis"},
    {"email": "dan@illinimedia.com", "name": "Dan Wilson"},
]


def seed_dummy_shifts(reference_date: date = None):
    """
    Populate the current week with dummy shift assignments.
    Assigns roughly half the slots to dummy editors so you can
    test swapping, picking up drops, etc.
    """
    sunday, saturday = get_week_bounds(reference_date)

    # Assignments: (day_offset_from_sunday, start_hour, editor_index)
    assignments = [
        # Sunday
        (0, 8, 0),  # Alice: Sun 8-10am
        (0, 14, 1),  # Bob: Sun 2-4pm
        (0, 20, 2),  # Carol: Sun 8-10pm
        # Monday
        (1, 8, 1),  # Bob: Mon 8-10am
        (1, 10, 0),  # Alice: Mon 10am-12pm
        (1, 14, 3),  # Dan: Mon 2-4pm
        (1, 18, 2),  # Carol: Mon 6-8pm
        # Tuesday
        (2, 8, 2),  # Carol: Tue 8-10am
        (2, 12, 3),  # Dan: Tue 12-2pm
        (2, 16, 0),  # Alice: Tue 4-6pm
        (2, 20, 1),  # Bob: Tue 8-10pm
        # Wednesday
        (3, 10, 1),  # Bob: Wed 10am-12pm
        (3, 14, 2),  # Carol: Wed 2-4pm
        (3, 18, 3),  # Dan: Wed 6-8pm
        # Thursday
        (4, 8, 0),  # Alice: Thu 8-10am
        (4, 12, 3),  # Dan: Thu 12-2pm
        (4, 16, 1),  # Bob: Thu 4-6pm
        (4, 22, 2),  # Carol: Thu 10pm-12am
        # Friday
        (5, 10, 2),  # Carol: Fri 10am-12pm
        (5, 14, 0),  # Alice: Fri 2-4pm
        (5, 20, 3),  # Dan: Fri 8-10pm
        # Saturday
        (6, 8, 3),  # Dan: Sat 8-10am
        (6, 14, 1),  # Bob: Sat 2-4pm
        (6, 18, 0),  # Alice: Sat 6-8pm
    ]

    with dbclient.context():
        for day_offset, hour, editor_idx in assignments:
            d = sunday + timedelta(days=day_offset)
            editor = DUMMY_EDITORS[editor_idx]
            assign_shift(d, hour, editor["email"], editor["name"])

        # Mark some shifts as up for drop
        from util.shift_utils import mark_up_for_drop

        up_for_drop = [
            (1, 8),  # Bob's Mon 8-10am
            (2, 16),  # Alice's Tue 4-6pm
            (4, 16),  # Bob's Thu 4-6pm
            (6, 14),  # Bob's Sat 2-4pm
        ]
        for day_offset, hour in up_for_drop:
            d = sunday + timedelta(days=day_offset)
            mark_up_for_drop(d, hour)

    print(
        f"Seeded {len(assignments)} dummy shifts ({len(up_for_drop)} up for drop) for week of {sunday}"
    )
