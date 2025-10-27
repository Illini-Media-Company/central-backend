from __future__ import annotations
import re
from collections import deque
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
    _check_connectivity(cw.grid)
    _check_min_word_len(spans)

    _check_clue_integrity(cw, spans)
    _check_answers_list(cw, spans)

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
        raise ValueError(f"origin must be 'manual' or 'auto', got {cw.origin!r}.")
    if not cw.article_link:
        raise ValueError("article_link is required.")
    if not isinstance(cw.clues, list) or not cw.clues:
        raise ValueError("clues must be a non-empty list.")
    if cw.origin == "manual" and not cw.created_by:
        raise ValueError("created_by is required for manual crosswords.")


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
        raise ValueError(f"Too many black cells: {num_blacks} > {MAX_BLACKS}.")


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
    # first number the cells in the grid that start a span
    # then make span objects by going over those cells

    next_num = 1
    number_at: Dict[Tuple[int, int], int] = {}

    for r in range(GRID_SIZE):
        for c in range(GRID_SIZE):
            if grid[r][c] == "#":
                continue
            starts_across = c == 0 or grid[r][c - 1] == "#"
            starts_down = r == 0 or grid[r - 1][c] == "#"
            if starts_across or starts_down:
                number_at[(r, c)] = next_num
                next_num += 1

    across: List[_Span] = []
    down: List[_Span] = []

    for r in range(GRID_SIZE):
        c = 0
        while c < GRID_SIZE:
            if grid[r][c] != "#" and (c == 0 or grid[r][c - 1] == "#"):
                cells: List[Tuple[int, int]] = []
                j = c
                while j < GRID_SIZE and grid[r][j] != "#":
                    cells.append((r, j))
                    j += 1
                num = number_at.get((r, c))
                if num is not None:
                    across.append(_Span("across", num, cells, grid))
                c = j
            else:
                c += 1

    for c in range(GRID_SIZE):
        r = 0
        while r < GRID_SIZE:
            if grid[r][c] != "#" and (r == 0 or grid[r - 1][c] == "#"):
                cells: List[Tuple[int, int]] = []
                i = r
                while i < GRID_SIZE and grid[i][c] != "#":
                    cells.append((i, c))
                    i += 1
                num = number_at.get((r, c))
                if num is not None:
                    down.append(_Span("down", num, cells, grid))
                r = i
            else:
                r += 1

    return {"across": across, "down": down}


def _check_connectivity(grid: List[List[str]]) -> None:
    """Using BFS to check all white cells are 4-way connected (no isolated islands)."""
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


def _check_min_word_len(spans: Dict[str, List[_Span]]) -> None:
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            if sp.length < MIN_WORD_LEN:
                raise ValueError(
                    f"{d.title()} entry #{sp.number} is too short ({sp.length} < {MIN_WORD_LEN})."
                )


def _check_clue_integrity(cw, spans: Dict[str, List[_Span]]) -> None:
    # clue map keys: (direction, number)
    for cl in cw.clues:
        if cl.direction not in VALID_DIRECTIONS:
            raise ValueError("Every clue.direction must be 'across' or 'down'.")

    clue_map: Dict[Tuple[str, int], object] = {}
    for cl in cw.clues:
        key = (cl.direction, cl.number)
        if key in clue_map:
            raise ValueError(f"Duplicate clue number {cl.number} in {cl.direction}.")
        clue_map[key] = cl

    # Ensure each span has a valid clue and matches letters/length
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            key = (d, sp.number)
            if key not in clue_map:
                raise ValueError(f"Missing {d} clue for number {sp.number}.")
            clue = clue_map[key]

            ans = (clue.answer or "").strip().upper()
            if not ans or not ans.isalpha():
                raise ValueError(
                    f"{d.title()} #{sp.number} answer must be uppercase A–Z letters only; got {clue.answer!r}."
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
    valid_keys = {
        (sp.direction, sp.number) for d in VALID_DIRECTIONS for sp in spans[d]
    }
    extras = [
        f"{cl.direction} #{cl.number}"
        for cl in cw.clues
        if (cl.direction, cl.number) not in valid_keys
    ]
    if extras:
        raise ValueError(f"Clues that do not map to any span: {', '.join(extras)}.")


def _check_answers_list(cw, spans: Dict[str, List[_Span]]) -> None:
    """
    Ensure cw.answers equals the set of answers derived from clues (ignoring order/case).
    """
    # Map (direction, number) -> answer from clues
    clue_answer: Dict[Tuple[str, int], str] = {}
    for cl in cw.clues:
        clue_answer[(cl.direction, cl.number)] = (cl.answer or "").strip().upper()

    # Expected set from spans (across then down)
    expected: List[str] = []
    for d in VALID_DIRECTIONS:
        for sp in spans[d]:
            expected.append(clue_answer[(sp.direction, sp.number)])

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
