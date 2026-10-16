from __future__ import annotations

from dataclasses import dataclass

from .model import EffectivePuzzle, Puzzle, resolve_marks


@dataclass(frozen=True)
class Violation:
    rule_id: str
    coordinates: tuple[tuple[int, int], ...]
    reason: str


def validate_solution(
    puzzle: Puzzle | EffectivePuzzle,
    columns: list[int] | tuple[int, ...],
    mark_policy: str = "base",
) -> list[Violation]:
    effective = puzzle if isinstance(puzzle, EffectivePuzzle) else resolve_marks(puzzle, mark_policy)
    size = effective.size
    errors: list[Violation] = []
    if not isinstance(columns, (list, tuple)) or len(columns) != size:
        return [Violation("R1", (), f"解必須包含 {size} 個欄號")]
    for row, column in enumerate(columns):
        if isinstance(column, bool) or not isinstance(column, int) or not 0 <= column < size:
            errors.append(Violation("R1", ((row, column),), "欄號必須是棋盤內的整數"))
    if errors:
        return errors

    cats = [(row, column) for row, column in enumerate(columns)]
    for column in range(size):
        occupants = [cell for cell in cats if cell[1] == column]
        if len(occupants) > 1:
            errors.append(Violation("R2", tuple(occupants), "同一欄有多隻貓"))
    region_cells: dict[str, list[tuple[int, int]]] = {}
    for row, column in cats:
        region_cells.setdefault(effective.regions[row][column], []).append((row, column))
    for region, occupants in region_cells.items():
        if len(occupants) > 1:
            errors.append(Violation("R3", tuple(occupants), f"region {region!r} 有多隻貓"))
    for index, first in enumerate(cats):
        for second in cats[index + 1 :]:
            if max(abs(first[0] - second[0]), abs(first[1] - second[1])) == 1:
                errors.append(Violation("R4", (first, second), "兩隻貓八方向相鄰"))
    selected = set(cats)
    for cell in sorted(effective.fixed_cats - selected):
        errors.append(Violation("FIXED", (cell,), "固定貓位置沒有貓"))
    for cell in sorted(effective.blocked_cells & selected):
        errors.append(Violation("BLOCKED", (cell,), "禁止格有貓"))
    return errors
