from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .model import EffectivePuzzle, InputValidationError, Puzzle, resolve_marks
from .validator import validate_solution


@dataclass(frozen=True)
class SolveOptions:
    mode: str = "classify"
    mark_policy: str = "base"
    timeout_ms: int | None = 5000
    max_nodes: int | None = None
    cancel_check: Callable[[], bool] | None = field(default=None, compare=False, repr=False)
    clock: Callable[[], float] = field(default=time.monotonic, compare=False, repr=False)


@dataclass
class SolveResult:
    status: str
    uniqueness: str
    search_complete: bool
    solutions: list[list[int]]
    nodes: int
    elapsed_ms: int
    errors: list[str]
    mark_policy: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "uniqueness": self.uniqueness,
            "search_complete": self.search_complete,
            "solutions": self.solutions,
            "stats": {"nodes": self.nodes, "elapsed_ms": self.elapsed_ms},
            "errors": self.errors,
            "mark_policy": self.mark_policy,
            "coordinate_base": 0,
        }


def _unsat_result(policy: str, start: float, clock: Callable[[], float]) -> SolveResult:
    return SolveResult("UNSAT", "NOT_APPLICABLE", True, [], 0, int((clock() - start) * 1000), [], policy)


def solve(puzzle: Puzzle, options: SolveOptions | None = None) -> SolveResult:
    options = options or SolveOptions()
    policy = options.mark_policy
    try:
        if options.mode not in {"first", "classify", "all"}:
            raise InputValidationError("mode: 必須是 first、classify 或 all")
        if policy not in {"base", "trust-cats", "trust-all"}:
            raise InputValidationError("mark_policy: 必須是 base、trust-cats 或 trust-all")
        if options.timeout_ms is not None and (
            isinstance(options.timeout_ms, bool)
            or not isinstance(options.timeout_ms, int)
            or options.timeout_ms <= 0
        ):
            raise InputValidationError("timeout_ms: 必須是正整數或 null")
        if options.max_nodes is not None and (
            isinstance(options.max_nodes, bool)
            or not isinstance(options.max_nodes, int)
            or options.max_nodes < 0
        ):
            raise InputValidationError("max_nodes: 必須是非負整數或 null")
        if options.cancel_check is not None and not callable(options.cancel_check):
            raise InputValidationError("cancel_check: 必須可呼叫")
        if not isinstance(puzzle, Puzzle):
            raise InputValidationError("puzzle: 必須是已驗證的 Puzzle")
        effective = resolve_marks(puzzle, policy)
    except InputValidationError as exc:
        return SolveResult(
            "INVALID_INPUT", "NOT_APPLICABLE", False, [], 0, 0, [exc.message], policy
        )

    clock = options.clock
    start = clock()
    size = effective.size
    fixed_by_row: dict[int, int] = {}
    for row, column in effective.fixed_cats:
        if row in fixed_by_row and fixed_by_row[row] != column:
            return _unsat_result(policy, start, clock)
        fixed_by_row[row] = column
    fixed_cells = sorted(effective.fixed_cats)
    for index, first in enumerate(fixed_cells):
        for second in fixed_cells[index + 1 :]:
            if (
                first[0] == second[0]
                or first[1] == second[1]
                or effective.regions[first[0]][first[1]] == effective.regions[second[0]][second[1]]
                or max(abs(first[0] - second[0]), abs(first[1] - second[1])) == 1
            ):
                return _unsat_result(policy, start, clock)
    if effective.fixed_cats & effective.blocked_cells:
        return _unsat_result(policy, start, clock)

    assigned: dict[int, int] = {}
    for row, column in fixed_by_row.items():
        assigned[row] = column

    solutions: list[list[int]] = []
    nodes = 0
    deadline = start + options.timeout_ms / 1000 if options.timeout_ms is not None else None
    abort_status: str | None = None
    early_stop = False

    def interrupted() -> str | None:
        if options.cancel_check is not None and options.cancel_check():
            return "CANCELLED"
        if deadline is not None and clock() >= deadline:
            return "TIMEOUT"
        if options.max_nodes is not None and nodes >= options.max_nodes:
            return "NODE_LIMIT"
        return None

    def domain(row: int) -> list[int]:
        candidates: list[int] = []
        for column in range(size):
            if row in fixed_by_row and fixed_by_row[row] != column:
                continue
            if (row, column) in effective.blocked_cells:
                continue
            if any(existing_column == column for existing_column in assigned.values()):
                continue
            region = effective.regions[row][column]
            if any(
                effective.regions[existing_row][existing_column] == region
                for existing_row, existing_column in assigned.items()
            ):
                continue
            if any(
                abs(existing_row - row) == 1
                and abs(existing_column - column) <= 1
                for existing_row, existing_column in assigned.items()
            ):
                continue
            candidates.append(column)
        return candidates

    def has_full_matching(items: list[int], choices: dict[int, set[int]]) -> bool:
        matched: dict[int, int] = {}

        def augment(item: int, seen: set[int]) -> bool:
            for choice in sorted(choices[item]):
                if choice in seen:
                    continue
                seen.add(choice)
                if choice not in matched or augment(matched[choice], seen):
                    matched[choice] = item
                    return True
            return False

        for item in sorted(items, key=lambda value: (len(choices[value]), value)):
            if not augment(item, set()):
                return False
        return True

    def search() -> str:
        nonlocal nodes, abort_status, early_stop
        interrupted_status = interrupted()
        if interrupted_status:
            abort_status = interrupted_status
            return "ABORTED"
        nodes += 1
        if len(assigned) == size:
            solution = [assigned[row] for row in range(size)]
            if validate_solution(effective, solution):
                raise RuntimeError("solver 產生未通過獨立 validator 的解")
            solutions.append(solution)
            if (options.mode == "first" and len(solutions) == 1) or (
                options.mode == "classify" and len(solutions) == 2
            ):
                early_stop = True
                return "EARLY"
            return "EXHAUSTED"

        unassigned = [row for row in range(size) if row not in assigned]
        domains = {row: domain(row) for row in unassigned}
        if any(not candidates for candidates in domains.values()):
            return "EXHAUSTED"

        region_domains = {
            row: {effective.regions[row][column] for column in candidates}
            for row, candidates in domains.items()
        }
        if not has_full_matching(list(domains), region_domains):
            return "EXHAUSTED"
        column_domains = {row: set(candidates) for row, candidates in domains.items()}
        if not has_full_matching(list(domains), column_domains):
            return "EXHAUSTED"

        used_columns = {column for column in assigned.values()}
        used_regions = {
            effective.regions[row][column] for row, column in assigned.items()
        }
        for column in range(size):
            if column not in used_columns and not any(
                column in candidates for candidates in domains.values()
            ):
                return "EXHAUSTED"
        remaining_regions = set(
            region for row in effective.regions for region in row
        ) - used_regions
        for region in remaining_regions:
            if not any(
                effective.regions[row][column] == region
                for row, candidates in domains.items()
                for column in candidates
            ):
                return "EXHAUSTED"

        row = min(unassigned, key=lambda candidate_row: (len(domains[candidate_row]), candidate_row))
        for column in domains[row]:
            assigned[row] = column
            result = search()
            del assigned[row]
            if result in {"ABORTED", "EARLY"}:
                return result
        return "EXHAUSTED"

    exit_kind = search()
    elapsed = int((clock() - start) * 1000)
    if exit_kind == "ABORTED":
        uniqueness = "MULTIPLE" if len(solutions) >= 2 else "UNKNOWN"
        return SolveResult(
            abort_status or "TIMEOUT", uniqueness, False, solutions, nodes, elapsed, [], policy
        )
    if early_stop:
        return SolveResult("SOLVED", "UNKNOWN" if options.mode == "first" else "MULTIPLE",
                           False, solutions, nodes, elapsed, [], policy)
    if not solutions:
        return SolveResult("UNSAT", "NOT_APPLICABLE", True, [], nodes, elapsed, [], policy)
    uniqueness = "UNIQUE" if len(solutions) == 1 else "MULTIPLE"
    return SolveResult("SOLVED", uniqueness, True, solutions, nodes, elapsed, [], policy)
