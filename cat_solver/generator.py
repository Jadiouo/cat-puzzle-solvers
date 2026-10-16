from __future__ import annotations

import random
from typing import Any

from .model import InputValidationError, parse_puzzle
from .solver import SolveOptions, solve
from .validator import validate_solution


_DIFFICULTIES = {"easy", "medium", "hard"}


def _make_solution(size: int, rng: random.Random) -> list[int]:
    solution: list[int | None] = [None] * size
    used: set[int] = set()
    steps = 0

    def place(row: int) -> bool:
        nonlocal steps
        steps += 1
        if row == size:
            return True
        for column in rng.sample(range(size), size):
            if column in used:
                continue
            if row and abs(column - int(solution[row - 1])) <= 1:
                continue
            solution[row] = column
            used.add(column)
            if place(row + 1):
                return True
            used.remove(column)
            solution[row] = None
            if steps > 250_000:
                return False
        return False

    if not place(0):
        raise InputValidationError(f"無法為 size={size} 建立合法貓位置")
    return [int(column) for column in solution]


def generate_puzzle(size: int, difficulty: str = "medium", seed: int = 0) -> dict[str, Any]:
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 25:
        raise InputValidationError("size: 必須是 1..25 的整數")
    if size in {2, 3}:
        raise InputValidationError(f"size={size} 在規則下無合法解；可用尺寸為 1 或 4..25")
    if difficulty not in _DIFFICULTIES:
        raise InputValidationError("difficulty: 必須是 easy、medium 或 hard")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise InputValidationError("seed: 必須是整數")

    rng = random.Random(seed)
    columns = _make_solution(size, rng)
    row_order = rng.sample(range(size), size)
    region_for_row = {row: f"R{index:02d}" for index, row in enumerate(row_order)}
    regions: list[list[str]] = []
    for row in range(size):
        own_region = region_for_row[row]
        position = row_order.index(row)
        successor = region_for_row[row_order[position + 1]] if position + 1 < size else own_region
        regions.append([
            own_region if column == columns[row] else successor
            for column in range(size)
        ])

    clue_counts = {
        "easy": (size + 1) // 2,
        "medium": size // 4,
        "hard": 0,
    }
    cat_rows = rng.sample(range(size), clue_counts[difficulty])
    fixed_cats = [[row, columns[row]] for row in sorted(cat_rows)]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "id": f"generated_n{size}_{difficulty}_{seed}",
        "size": size,
        "regions": regions,
        "fixed_cats": fixed_cats,
        "blocked_cells": [],
        "annotations": {"observed_cats": [], "observed_crosses": []},
        "generator": {"difficulty": difficulty, "seed": seed},
    }

    puzzle = parse_puzzle(payload)
    result = solve(
        puzzle,
        SolveOptions(mode="classify", mark_policy="base", timeout_ms=None, max_nodes=None),
    )
    if result.status != "SOLVED" or result.uniqueness != "UNIQUE":
        raise RuntimeError(
            f"generator correctness check failed: {result.status}/{result.uniqueness}"
        )
    if result.solutions[0] != columns or validate_solution(puzzle, columns):
        raise RuntimeError("generator's constructed answer failed independent validation")
    return payload
