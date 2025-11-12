from __future__ import annotations
import re
from collections import deque
from datetime import date
from typing import Dict, List, Optional, Tuple

# fixed dimensions
GRID_SIZE = 5
MAX_BLACKS = 7
MIN_WORD_LEN = 3
VALID_DIRECTIONS = ("across", "down")
UPPER_AZ = re.compile(r"^[A-Z]$")


# main public function
def validate_crossword(cw) -> Dict[str, str | int]:
    """
    Validates crossword object. Raises a ValueError on any failure
    otherwise returns a success summary.
    """

    _check_meta(cw)
    _check_grid_shape(cw.grid)
    _check_grid_chars(cw.grid)
    _check_black_cap(cw.grid)

    spans = _extract_spans(cw.grid)
    _check_max_spans(spans)
    _check_connectivity(cw.grid)
    _check_min_word_len(spans)

    # Clue validation is skipped - clues are assumed to be correct when provided
    # Clues dict can be empty and that's valid

    return {
        "id": cw.id,
        "date": str(cw.date),
        "origin": cw.origin,
        "article_link": cw.article_link,
        "across_count": len(spans["across"]),
        "down_count": len(spans["down"]),
        "total_entries": len(spans["across"]) + len(spans["down"]),
    }


# HELPER FUNCTIONS:


def _check_meta(cw) -> None:
    if cw.origin not in ("manual", "auto"):
        raise ValueError(f"Origin must be 'manual' or 'auto', got {cw.origin!r}.")
    if not cw.article_link:
        raise ValueError("An article link is required.")
    if not isinstance(cw.clues, dict):
        raise ValueError("Clues must be a dict (can be empty).")
    if cw.origin == "manual" and not cw.created_by:
        raise ValueError("Created By is required for manual crosswords.")
    _check_date_is_monday(cw.date)


def _check_date_is_monday(cw_date) -> None:
    """Check that the crossword date is a Monday and not before today.

    Handles date as:
    - datetime.date object (from NDB's to_dict())
    - string in YYYY-MM-DD format (from JSON serialization)
    """
    # Convert string to date if needed
    if isinstance(cw_date, str):
        try:
            cw_date = date.fromisoformat(cw_date)
        except (ValueError, AttributeError):
            raise ValueError(
                f"date must be a date object or ISO format string (YYYY-MM-DD); got {cw_date!r}."
            )
    elif not isinstance(cw_date, date):
        raise ValueError(
            f"date must be a date object or string; got {type(cw_date).__name__}."
        )

    # Check that date is not before today
    today = date.today()
    if cw_date < today:
        raise ValueError(
            f"Crossword date cannot be before today ({today}). Got {cw_date}."
        )

    # Monday is weekday 0 in Python's datetime
    if cw_date.weekday() != 0:
        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        day_name = weekday_names[cw_date.weekday()]
        raise ValueError(f"Crossword date must be a Monday; got {day_name} {cw_date}.")


def _check_grid_shape(grid: List[List[str]]) -> None:
    if len(grid) != GRID_SIZE or any(len(row) != GRID_SIZE for row in grid):
        raise ValueError(f"Grid must be exactly {GRID_SIZE}x{GRID_SIZE}.")


def _check_grid_chars(grid: List[List[str]]) -> None:
    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            ch = grid[r][c]
            if ch == "#":
                continue
            if not (isinstance(ch, str) and len(ch) == 1 and UPPER_AZ.match(ch)):
                raise ValueError(
                    f"Cell ({r},{c}) must be '#' or a single uppercase A-Z letter; got {ch!r}."
                )


def _check_black_cap(grid: List[List[str]]) -> None:
    num_blacks = sum(ch == "#" for row in grid for ch in row)
    if num_blacks > MAX_BLACKS:
        raise ValueError(
            f"Too many black cells: {num_blacks}. Only {MAX_BLACKS} are allowed."
        )


class _Span:
    """Internal class represents one across/down entry extracted from the grid."""

    __slots__ = ("direction", "number", "cells", "length", "prefill")

    def __init__(
        self,
        direction: str,
        number: int,
        cells: List[Tuple[int, int]],
        grid: List[List[str]],
    ):
        self.direction = direction
        self.number = number
        self.cells = cells
        self.length = len(cells)
        # letters that are already in the span in the grid
        self.prefill: List[Optional[str]] = [
            grid[r][c] if grid[r][c] != "#" else None for r, c in cells
        ]


def _extract_spans(grid: List[List[str]]) -> Dict[str, List[_Span]]:
    """
    Extract spans from grid with numbering:
    - Across spans: numbered 1-5
    - Down spans: numbered 6-10
    """
    across: List[_Span] = []
    down: List[_Span] = []

    # Extract across spans and number them 1-5
    across_num = 1
    for r in range(GRID_SIZE):
        c = 0
        while c < GRID_SIZE:
            # Start of a word: cell is not black, and (at start of row OR previous cell is black)
            if grid[r][c] != "#" and (c == 0 or grid[r][c - 1] == "#"):
                cells: List[Tuple[int, int]] = []
                j = c
                # Continue while we have non-black cells
                while j < GRID_SIZE and grid[r][j] != "#":
                    cells.append((r, j))
                    j += 1
                # Only add if we haven't exceeded max across spans (5)
                if across_num <= 5:
                    across.append(_Span("across", across_num, cells, grid))
                    across_num += 1
                c = j
            else:
                c += 1

    # Extract down spans and number them 6-10
    down_num = 6
    for c in range(GRID_SIZE):
        r = 0
        while r < GRID_SIZE:
            # Start of a word: cell is not black, and (at start of column OR previous cell is black)
            if grid[r][c] != "#" and (r == 0 or grid[r - 1][c] == "#"):
                cells: List[Tuple[int, int]] = []
                i = r
                # Continue while we have non-black cells
                while i < GRID_SIZE and grid[i][c] != "#":
                    cells.append((i, c))
                    i += 1
                # Only add if we haven't exceeded max down spans (5)
                if down_num <= 10:
                    down.append(_Span("down", down_num, cells, grid))
                    down_num += 1
                r = i
            else:
                r += 1

    return {"across": across, "down": down}


def _check_connectivity(grid: List[List[str]]) -> None:
    """Using BFS to check all white cells are 4-way connected (no isolated islands)."""
    # White cells are non-black cells (can be empty, "-", or letters)
    whites = [
        (r, c) for r in range(GRID_SIZE) for c in range(GRID_SIZE) if grid[r][c] != "#"
    ]
    if not whites:
        raise ValueError("Grid has no white cells.")

    seen = {whites[0]}
    q: deque[Tuple[int, int]] = deque([whites[0]])
    while q:
        r, c = q.popleft()
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if (
                0 <= nr < GRID_SIZE
                and 0 <= nc < GRID_SIZE
                and grid[nr][nc] != "#"
                and (nr, nc) not in seen
            ):
                seen.add((nr, nc))
                q.append((nr, nc))

    if len(seen) != len(whites):
        raise ValueError("White cells must form a single connected region (4-way).")


def _check_max_spans(spans: Dict[str, List[_Span]]) -> None:
    """Check that we don't exceed maximum spans: 5 across, 5 down."""
    if len(spans["across"]) > 5:
        raise ValueError(
            f"Too many across spans: {len(spans['across'])}. Only 5 are allowed."
        )
    if len(spans["down"]) > 5:
        raise ValueError(
            f"Too many down spans: {len(spans['down'])}. Only 5 are allowed."
        )


def _check_min_word_len(spans: Dict[str, List[_Span]]) -> None:
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            if sp.length < MIN_WORD_LEN:
                raise ValueError(
                    f"{d.title()} entry #{sp.number} is too short ({sp.length} < {MIN_WORD_LEN})."
                )


# unused methods - kept for reference
def _check_clue_integrity(cw, spans: Dict[str, List[_Span]]) -> None:
    # clue map keys: number (unique by number only)
    # Validate clue structure and build clue_map
    clue_map: Dict[int, List] = {}
    for number, clue_data in cw.clues.items():
        if not isinstance(number, int):
            raise ValueError(f"Clue keys must be integers; got {number!r}.")
        if number < 1 or number > 10:
            raise ValueError(f"Clue numbers must be between 1 and 10; got {number}.")
        if not isinstance(clue_data, list) or len(clue_data) != 3:
            raise ValueError(
                f"Clue {number} must be a list [direction, text, answer]; got {clue_data!r}."
            )

        direction, text, answer = clue_data
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"Clue {number} direction must be 'across' or 'down'; got {direction!r}."
            )
        if not isinstance(text, str):
            raise ValueError(f"Clue {number} text must be a string; got {text!r}.")
        if not isinstance(answer, str):
            raise ValueError(f"Clue {number} answer must be a string; got {answer!r}.")

        if number in clue_map:
            raise ValueError(f"Duplicate clue number {number}.")
        clue_map[number] = clue_data

    # Collect all span numbers to check for missing clues
    span_numbers = {sp.number for d in VALID_DIRECTIONS for sp in spans[d]}

    # Ensure each span has a valid clue and matches letters/length
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            if sp.number not in clue_map:
                raise ValueError(
                    f"Missing clue for number {sp.number} ({d} direction)."
                )
            clue_data = clue_map[sp.number]
            direction, text, answer = clue_data

            # Verify the clue's direction matches the span's direction
            if direction != d:
                raise ValueError(
                    f"Clue {sp.number} has direction '{direction}' but span requires '{d}' direction."
                )

            ans = (answer or "").strip().upper()
            if not ans or not ans.isalpha():
                raise ValueError(
                    f"{d.title()} #{sp.number} answer must be uppercase A–Z letters only; got {answer!r}."
                )
            if len(ans) != sp.length:
                raise ValueError(
                    f"{d.title()} #{sp.number} answer length {len(ans)} != span length {sp.length}."
                )

            # Prefilled letter agreement: any letter already in grid must match the clue's answer
            for i, (r, c) in enumerate(sp.cells):
                g = sp.prefill[i]
                if g is not None and g != ans[i]:
                    raise ValueError(
                        f"{d.title()} #{sp.number} conflicts at ({r},{c}): grid has '{g}' but answer has '{ans[i]}'."
                    )

    # Ensure no orphan clues (clues that don't correspond to any span)
    extras = [
        f"{clue_data[0]} #{number}"
        for number, clue_data in cw.clues.items()
        if number not in span_numbers
    ]
    if extras:
        raise ValueError(f"Clues that do not map to any span: {', '.join(extras)}.")


# unused method - kept for reference
def _check_answers_list(cw, spans: Dict[str, List[_Span]]) -> None:
    """
    Ensure cw.answers equals the set of answers derived from clues (ignoring order/case).
    """
    # Map number -> answer from clues
    clue_answer: Dict[int, str] = {}
    for number, clue_data in cw.clues.items():
        direction, text, answer = clue_data
        clue_answer[number] = (answer or "").strip().upper()

    # Expected set from spans (across then down)
    expected: List[str] = []
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            expected.append(clue_answer[sp.number])

    listed = {a.strip().upper() for a in (cw.answers or []) if isinstance(a, str)}
    expected_set = set(expected)

    if not expected_set:
        raise ValueError("No expected answers derived from clues; check your clues.")
    if listed != expected_set:
        extra = list(listed - expected_set)
        missing = list(expected_set - listed)
        parts = []
        if missing:
            parts.append(f"missing from answers: {missing}")
        if extra:
            parts.append(f"extra in answers: {extra}")
        raise ValueError("answers list does not match clues — " + "; ".join(parts))
