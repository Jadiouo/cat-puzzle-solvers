from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InputValidationError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Puzzle:
    size: int
    regions: tuple[tuple[str, ...], ...]
    fixed_cats: frozenset[tuple[int, int]] = frozenset()
    blocked_cells: frozenset[tuple[int, int]] = frozenset()
    observed_cats: frozenset[tuple[int, int]] = frozenset()
    observed_crosses: frozenset[tuple[int, int]] = frozenset()
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class EffectivePuzzle:
    puzzle: Puzzle
    mark_policy: str
    fixed_cats: frozenset[tuple[int, int]]
    blocked_cells: frozenset[tuple[int, int]]

    @property
    def size(self) -> int:
        return self.puzzle.size

    @property
    def regions(self) -> tuple[tuple[str, ...], ...]:
        return self.puzzle.regions


def _coordinates(payload: Any, field: str, size: int) -> frozenset[tuple[int, int]]:
    if not isinstance(payload, list):
        raise InputValidationError(f"{field}: 預期座標陣列")
    result: set[tuple[int, int]] = set()
    for index, pair in enumerate(payload):
        if not isinstance(pair, list) or len(pair) != 2:
            raise InputValidationError(f"{field}[{index}]: 預期 [row, column]")
        row, column = pair
        if any(isinstance(value, bool) or not isinstance(value, int) for value in pair):
            raise InputValidationError(f"{field}[{index}]: 座標必須是整數")
        if not (0 <= row < size and 0 <= column < size):
            raise InputValidationError(f"{field}[{index}]: 座標超出棋盤範圍")
        coordinate = (row, column)
        if coordinate in result:
            raise InputValidationError(f"{field}: 不可有重複座標 {list(coordinate)}")
        result.add(coordinate)
    return frozenset(result)


def parse_puzzle(payload: dict[str, Any]) -> Puzzle:
    if not isinstance(payload, dict):
        raise InputValidationError("$: 預期 JSON object")
    if payload.get("schema_version") != "1.0":
        raise InputValidationError("schema_version: 必須是 '1.0'")
    size = payload.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 25:
        raise InputValidationError("size: 必須是 1..25 的整數")
    rows = payload.get("regions")
    if not isinstance(rows, list) or len(rows) != size:
        raise InputValidationError(f"regions: 必須有 {size} 列")
    regions: list[tuple[str, ...]] = []
    ids: set[str] = set()
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != size:
            raise InputValidationError(f"regions[{row_index}]: 必須有 {size} 格")
        checked_row: list[str] = []
        for column_index, region in enumerate(row):
            if not isinstance(region, str) or not region.strip():
                raise InputValidationError(
                    f"regions[{row_index}][{column_index}]: region ID 必須是非空字串"
                )
            checked_row.append(region)
            ids.add(region)
        regions.append(tuple(checked_row))
    if len(ids) != size:
        raise InputValidationError(f"regions: 必須恰有 {size} 個不同 region ID")

    fixed = _coordinates(payload.get("fixed_cats", []), "fixed_cats", size)
    blocked = _coordinates(payload.get("blocked_cells", []), "blocked_cells", size)
    if "region_labels" in payload and not isinstance(payload["region_labels"], dict):
        raise InputValidationError("region_labels: 預期 object")
    annotations = payload.get("annotations", {})
    if not isinstance(annotations, dict):
        raise InputValidationError("annotations: 預期 object")
    observed_cats = _coordinates(
        annotations.get("observed_cats", []), "annotations.observed_cats", size
    )
    observed_crosses = _coordinates(
        annotations.get("observed_crosses", []), "annotations.observed_crosses", size
    )
    metadata = {
        key: value
        for key, value in payload.items()
        if key not in {
            "schema_version", "size", "regions", "fixed_cats", "blocked_cells", "annotations"
        }
    }
    return Puzzle(
        size=size,
        regions=tuple(regions),
        fixed_cats=fixed,
        blocked_cells=blocked,
        observed_cats=observed_cats,
        observed_crosses=observed_crosses,
        metadata=metadata,
    )


def resolve_marks(puzzle: Puzzle, policy: str = "base") -> EffectivePuzzle:
    if policy not in {"base", "trust-cats", "trust-all"}:
        raise InputValidationError("mark_policy: 必須是 base、trust-cats 或 trust-all")
    fixed = set(puzzle.fixed_cats)
    blocked = set(puzzle.blocked_cells)
    if policy in {"trust-cats", "trust-all"}:
        fixed.update(puzzle.observed_cats)
    if policy == "trust-all":
        blocked.update(puzzle.observed_crosses)
    return EffectivePuzzle(
        puzzle=puzzle,
        mark_policy=policy,
        fixed_cats=frozenset(fixed),
        blocked_cells=frozenset(blocked),
    )
