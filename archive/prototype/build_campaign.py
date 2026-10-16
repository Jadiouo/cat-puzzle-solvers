from __future__ import annotations

import json
import hashlib
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cat_solver.model import parse_puzzle
from cat_solver.solver import SolveOptions, solve
from cat_solver.validator import validate_solution

HERE = Path(__file__).resolve().parent
SEED_BASE = 20261012
TARGET_UNIQUE_CANDIDATES = 200
MIN_UNIQUE_BY_SIZE = 30
MAX_SEEDS_PER_SIZE = 3000


def puzzle_identity(candidate: dict[str, Any]) -> str:
    identity = [
        candidate["size"],
        candidate["regions"],
        sorted(candidate["blocked_cells"]),
    ]
    return json.dumps(identity, separators=(",", ":"), ensure_ascii=True)


def puzzle_fingerprint(candidate: dict[str, Any]) -> str:
    return hashlib.sha256(puzzle_identity(candidate).encode("utf-8")).hexdigest()


def make_answer(size: int, rng: random.Random) -> list[int]:
    answer = [-1] * size
    used_columns: set[int] = set()

    def place(row: int) -> bool:
        if row == size:
            return True
        for column in rng.sample(range(size), size):
            if column in used_columns or (
                row and abs(answer[row - 1] - column) <= 1
            ):
                continue
            answer[row] = column
            used_columns.add(column)
            if place(row + 1):
                return True
            used_columns.remove(column)
        return False

    if not place(0):
        raise RuntimeError(f"無法建立 size={size} 的合法答案")
    return answer


def make_connected_regions(
    size: int, answer: list[int], rng: random.Random
) -> list[list[str]] | None:
    owners = [[-1] * size for _ in range(size)]
    owner_sizes = [0] * size
    for row, column in enumerate(answer):
        owners[row][column] = row
        owner_sizes[row] = 1
    unassigned = {
        (row, column)
        for row in range(size)
        for column in range(size)
        if owners[row][column] == -1
    }

    nodes = 0

    def grow() -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > 100_000:
            return False
        if not unassigned:
            return all(region_size == size for region_size in owner_sizes)

        frontier: list[tuple[int, int, list[int]]] = []
        for row, column in sorted(unassigned):
            neighbor_regions = {
                owners[next_row][next_column]
                for next_row, next_column in (
                    (row - 1, column),
                    (row + 1, column),
                    (row, column - 1),
                    (row, column + 1),
                )
                if 0 <= next_row < size
                and 0 <= next_column < size
                and owners[next_row][next_column] >= 0
                and owner_sizes[owners[next_row][next_column]] < size
            }
            if neighbor_regions:
                frontier.append((row, column, sorted(neighbor_regions)))
        if not frontier:
            return False

        fewest_owners = min(len(owners_for_cell) for _, _, owners_for_cell in frontier)
        choices = [
            item for item in frontier if len(item[2]) == fewest_owners
        ]
        rng.shuffle(choices)
        for row, column, neighboring_regions in choices:
            rng.shuffle(neighboring_regions)
            for owner in neighboring_regions:
                owners[row][column] = owner
                owner_sizes[owner] += 1
                unassigned.remove((row, column))
                if grow():
                    return True
                unassigned.add((row, column))
                owner_sizes[owner] -= 1
                owners[row][column] = -1
        return False

    if not grow():
        return None

    return [[f"R{owner:02d}" for owner in row] for row in owners]


def search_profile(payload: dict[str, Any]) -> dict[str, int | float]:
    size = payload["size"]
    regions = payload["regions"]
    blocked = {tuple(cell) for cell in payload["blocked_cells"]}
    assigned: dict[int, int] = {}
    nodes = 0
    decision_widths: list[int] = []

    def domain(row: int) -> list[int]:
        choices = []
        for column in range(size):
            if (row, column) in blocked:
                continue
            if column in assigned.values():
                continue
            region = regions[row][column]
            if any(regions[r][c] == region for r, c in assigned.items()):
                continue
            if any(abs(r - row) == 1 and abs(c - column) <= 1 for r, c in assigned.items()):
                continue
            choices.append(column)
        return choices

    def has_full_matching(items: list[int], choices: dict[int, set[Any]]) -> bool:
        matched: dict[Any, int] = {}

        def augment(item: int, seen: set[Any]) -> bool:
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

    def visit() -> None:
        nonlocal nodes
        nodes += 1
        if len(assigned) == size:
            return
        rows = [row for row in range(size) if row not in assigned]
        domains = {row: domain(row) for row in rows}
        if any(not candidates for candidates in domains.values()):
            return
        region_domains = {
            row: {regions[row][column] for column in candidates}
            for row, candidates in domains.items()
        }
        if not has_full_matching(rows, region_domains):
            return
        column_domains = {row: set(candidates) for row, candidates in domains.items()}
        if not has_full_matching(rows, column_domains):
            return
        used_columns = set(assigned.values())
        used_regions = {
            regions[row][column] for row, column in assigned.items()
        }
        if any(
            column not in used_columns
            and not any(column in candidates for candidates in domains.values())
            for column in range(size)
        ):
            return
        remaining_regions = {
            region for row in regions for region in row
        } - used_regions
        if any(
            not any(
                regions[row][column] == region
                for row, candidates in domains.items()
                for column in candidates
            )
            for region in remaining_regions
        ):
            return
        row = min(rows, key=lambda candidate: (len(domains[candidate]), candidate))
        decision_widths.append(len(domains[row]))
        for column in domains[row]:
            assigned[row] = column
            visit()
            del assigned[row]

    visit()
    return {
        "nodes": nodes,
        "decision_points": len(decision_widths),
        "mean_branching": (
            round(sum(decision_widths) / len(decision_widths), 3)
            if decision_widths
            else 0.0
        ),
    }


def generate_candidate(
    size: int, seed: int
) -> tuple[dict[str, Any] | None, str | None]:
    rng = random.Random(seed)
    answer = make_answer(size, rng)
    regions = make_connected_regions(size, answer, rng)
    if regions is None:
        return None, "partition"
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "size": size,
        "regions": regions,
        "fixed_cats": [],
        "blocked_cells": [],
    }
    puzzle = parse_puzzle(payload)
    if validate_solution(puzzle, answer):
        raise RuntimeError(f"獨立 validator 拒絕答案，seed={seed}")

    while True:
        result = solve(
            puzzle,
            SolveOptions(mode="classify", timeout_ms=None, max_nodes=None),
        )
        if result.status == "SOLVED" and result.uniqueness == "UNIQUE":
            if not result.search_complete or result.solutions != [answer]:
                raise RuntimeError(f"唯一解證明與目標答案不同，seed={seed}")
            profile = search_profile(payload)
            if profile["nodes"] != result.nodes:
                raise RuntimeError(
                    f"搜尋剖析節點與 production solver 不同 seed={seed}: "
                    f"{profile['nodes']} != {result.nodes}"
                )
            return {
                "size": size,
                "seed": seed,
                "regions": payload["regions"],
                "blocked_cells": payload["blocked_cells"],
                "fixed_cats": [],
                "solution": answer,
                "proof": {
                    "status": result.status,
                    "uniqueness": result.uniqueness,
                    "search_complete": result.search_complete,
                    "nodes": result.nodes,
                },
                "solver_profile": profile,
            }, None
        if result.status != "SOLVED" or result.uniqueness != "MULTIPLE":
            raise RuntimeError(
                f"拒絕不完整或非預期求解結果 seed={seed}: "
                f"{result.status}/{result.uniqueness}"
            )
        if len(payload["blocked_cells"]) >= size:
            return None, "clue_cap"
        alternative = next(
            solution for solution in result.solutions if solution != answer
        )
        blocked = next(
            (
                [row, column]
                for row, column in enumerate(alternative)
                if column != answer[row]
            ),
            None,
        )
        if blocked is None:
            raise RuntimeError(f"多解結果缺少替代解差異，seed={seed}")
        payload["blocked_cells"].append(blocked)
        puzzle = parse_puzzle(payload)


def connected_region_count(regions: list[list[str]], target: str) -> int:
    size = len(regions)
    cells = {
        (row, column)
        for row in range(size)
        for column in range(size)
        if regions[row][column] == target
    }
    start = next(iter(cells))
    reached = {start}
    pending = [start]
    while pending:
        row, column = pending.pop()
        for neighbor in (
            (row - 1, column),
            (row + 1, column),
            (row, column - 1),
            (row, column + 1),
        ):
            if neighbor in cells and neighbor not in reached:
                reached.add(neighbor)
                pending.append(neighbor)
    return len(reached)


def verify_candidate(candidate: dict[str, Any]) -> None:
    size = candidate["size"]
    regions = candidate["regions"]
    if len(regions) != size or any(len(row) != size for row in regions):
        raise RuntimeError("region 矩陣不是方形")
    ids = {region for row in regions for region in row}
    if len(ids) != size:
        raise RuntimeError("region 數量不等於棋盤尺寸")
    for region in ids:
        region_size = sum(
            cell == region for row in regions for cell in row
        )
        if region_size != size:
            raise RuntimeError(f"region {region} 必須剛好有 {size} 格")
        if connected_region_count(regions, region) != region_size:
            raise RuntimeError(f"region {region} 不四方向連通")
    if candidate["fixed_cats"]:
        raise RuntimeError("campaign 關卡不可預放貓")
    puzzle_payload = {
        "schema_version": "1.0",
        "size": size,
        "regions": regions,
        "fixed_cats": [],
        "blocked_cells": candidate["blocked_cells"],
    }
    puzzle = parse_puzzle(puzzle_payload)
    if validate_solution(puzzle, candidate["solution"]):
        raise RuntimeError("答案未通過獨立 validator")
    result = solve(
        puzzle,
        SolveOptions(mode="classify", timeout_ms=None, max_nodes=None),
    )
    if (
        result.status != "SOLVED"
        or result.uniqueness != "UNIQUE"
        or not result.search_complete
        or result.solutions != [candidate["solution"]]
    ):
        raise RuntimeError(
            f"重新求解未證明目標唯一: "
            f"{result.status}/{result.uniqueness}/{result.search_complete}"
        )
    if result.nodes != candidate["proof"]["nodes"]:
        raise RuntimeError("重新求解 node count 與保存的 proof 不同")
    if search_profile(puzzle_payload) != candidate["solver_profile"]:
        raise RuntimeError("重新計算的 solver profile 與保存值不同")


def main() -> None:
    candidates: list[dict[str, Any]] = []
    seen_identities: set[str] = set()
    seeds_tried = {4: 0, 5: 0}
    duplicate_candidates = 0
    partition_failures = 0
    clue_cap_failures = 0
    size_order = (4, 5)
    while (
        len(candidates) < TARGET_UNIQUE_CANDIDATES
        or any(
            sum(item["size"] == size for item in candidates) < MIN_UNIQUE_BY_SIZE
            for size in size_order
        )
    ):
        made_progress = False
        for size in size_order:
            if len(candidates) >= TARGET_UNIQUE_CANDIDATES and all(
                sum(item["size"] == candidate_size for item in candidates)
                >= MIN_UNIQUE_BY_SIZE
                for candidate_size in size_order
            ):
                break
            if seeds_tried[size] >= MAX_SEEDS_PER_SIZE:
                continue
            index = seeds_tried[size]
            seeds_tried[size] += 1
            made_progress = True
            seed = SEED_BASE + size * 100_000 + index
            candidate, rejected_for = generate_candidate(size, seed)
            if candidate is None:
                if rejected_for == "partition":
                    partition_failures += 1
                else:
                    clue_cap_failures += 1
                continue
            candidate["solver_score"] = round(
                10 * candidate["proof"]["nodes"]
                + 2 * size
                - len(candidate["blocked_cells"])
                + candidate["solver_profile"]["mean_branching"],
                3,
            )
            candidate["puzzle_fingerprint"] = puzzle_fingerprint(candidate)
            identity = puzzle_identity(candidate)
            if identity in seen_identities:
                duplicate_candidates += 1
                continue
            seen_identities.add(identity)
            candidates.append(candidate)
            if (
                sum(item["size"] == 4 for item in candidates) >= MIN_UNIQUE_BY_SIZE
                and sum(item["size"] == 5 for item in candidates) >= MIN_UNIQUE_BY_SIZE
                and len(candidates) >= TARGET_UNIQUE_CANDIDATES
            ):
                break
        if not made_progress:
            counts = {
                size: sum(item["size"] == size for item in candidates)
                for size in size_order
            }
            raise RuntimeError(
                f"候選耗盡前未達到 unique pool 需求：{len(candidates)} 題，"
                f"各尺寸={counts}，seed 數={seeds_tried}"
            )

    candidates.sort(
        key=lambda item: (
            item["solver_score"],
            item["proof"]["nodes"],
            item["size"],
            item["seed"],
        )
    )
    if len(candidates) < 100:
        raise RuntimeError(f"唯一候選只有 {len(candidates)}，不足 100 關")

    selected_indices = [
        round(index * (len(candidates) - 1) / 99) for index in range(100)
    ]
    selected = [candidates[index] for index in selected_indices]
    fingerprints = [item["puzzle_fingerprint"] for item in selected]
    identities = [puzzle_identity(item) for item in selected]
    assert len(fingerprints) == 100
    assert len(set(identities)) == 100, "campaign 100 關含重複 puzzle"
    assert len(set(fingerprints)) == 100, "campaign 100 關 fingerprint 重複"
    assert all(
        selected[index]["solver_score"] <= selected[index + 1]["solver_score"]
        for index in range(99)
    ), "campaign solver_score 必須非遞減"
    for level, candidate in enumerate(selected, start=1):
        verify_candidate(candidate)
        candidate["level"] = level
        candidate["difficulty"] = (
            "easy" if level <= 34 else "medium" if level <= 67 else "hard"
        )
    assert [item["difficulty"] for item in selected[:34]] == ["easy"] * 34
    assert [item["difficulty"] for item in selected[34:67]] == ["medium"] * 33
    assert [item["difficulty"] for item in selected[67:]] == ["hard"] * 33

    campaign = {
        "schema_version": "1.0",
        "campaign_id": "connected-cats-100",
        "generated_with_seed": SEED_BASE,
        "unique_puzzles": len(set(fingerprints)),
        "difficulty_method": (
            "按 solver_score 遞增取樣；score = complete_solver_nodes "
            "× 10 + 2*board_size - blocked_cell_count + mean_branching；"
            "每個 region 恰有 N 格且四方向連通"
        ),
        "levels": selected,
    }
    manifest = {
        "campaign_id": campaign["campaign_id"],
        "verified_levels": len(selected),
        "unique_puzzles": len(set(fingerprints)),
        "unique_proofs": sum(
            item["proof"]["uniqueness"] == "UNIQUE" for item in selected
        ),
        "fully_exhausted": all(
            item["proof"]["search_complete"] for item in selected
        ),
        "candidate_pool_size": len(candidates),
        "unique_candidate_puzzles": len(seen_identities),
        "seeds_tried_by_size": {str(size): count for size, count in seeds_tried.items()},
        "duplicate_candidates_rejected": duplicate_candidates,
        "candidates_rejected_for_partition": partition_failures,
        "candidates_rejected_for_clue_cap": clue_cap_failures,
        "score_formula": campaign["difficulty_method"],
        "difficulty_counts": {
            "easy": 34,
            "medium": 33,
            "hard": 33,
        },
        "levels": [
            {
                "level": item["level"],
                "size": item["size"],
                "difficulty": item["difficulty"],
                "solver_score": item["solver_score"],
                "seed": item["seed"],
                "puzzle_fingerprint": item["puzzle_fingerprint"],
                "blocked_count": len(item["blocked_cells"]),
                "fixed_cat_count": len(item["fixed_cats"]),
                "decision_points": item["solver_profile"]["decision_points"],
                "mean_branching": item["solver_profile"]["mean_branching"],
                **item["proof"],
            }
            for item in selected
        ],
    }
    (HERE / "campaign-100.json").write_text(
        json.dumps(campaign, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (HERE / "campaign-100-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    html_path = HERE / "cat-game-prototype.html"
    html = html_path.read_text(encoding="utf-8")
    start_marker = '<script type="application/json" id="campaign-data">'
    start = html.find(start_marker)
    end = html.find("</script>", start)
    if start < 0 or end < 0:
        raise RuntimeError("找不到 HTML campaign inline 區塊")
    start += len(start_marker)
    html_path.write_text(
        html[:start]
        + json.dumps(campaign, ensure_ascii=False, separators=(",", ":"))
        + html[end:],
        encoding="utf-8",
    )
    print(
        f"verified={len(selected)} unique={manifest['unique_proofs']} "
        f"nodes={min(x['proof']['nodes'] for x in selected)}.."
        f"{max(x['proof']['nodes'] for x in selected)} "
        f"score={selected[0]['solver_score']}..{selected[-1]['solver_score']}"
    )


if __name__ == "__main__":
    main()
