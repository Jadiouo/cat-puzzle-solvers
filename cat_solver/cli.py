from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .generator import generate_puzzle
from .model import InputValidationError, parse_puzzle
from .solver import SolveOptions, solve


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cat_solver",
        description="求解與生成每列、每欄、每區域各一隻貓且不相鄰的棋盤。",
    )
    commands = parser.add_subparsers(dest="command")
    solve_parser = commands.add_parser("solve", help="求解 JSON 棋盤")
    solve_parser.add_argument("input", help="JSON 檔案路徑，或 - 表示 stdin")
    solve_parser.add_argument("--mode", choices=("first", "classify", "all"), default="classify")
    solve_parser.add_argument(
        "--mark-policy", choices=("base", "trust-cats", "trust-all"), default="base"
    )
    solve_parser.add_argument("--timeout-ms", type=int, default=5000)
    solve_parser.add_argument("--max-nodes", type=int)
    output = solve_parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="輸出 JSON（預設格式）")
    output.add_argument("--human", action="store_true", help="以 1-based 座標顯示解")

    generate_parser = commands.add_parser("generate", help="生成唯一解關卡 JSON")
    generate_parser.add_argument("--size", type=int, required=True, help="棋盤尺寸 N")
    generate_parser.add_argument(
        "--difficulty", choices=("easy", "medium", "hard"), default="medium"
    )
    generate_parser.add_argument("--seed", type=int, default=0)
    generate_parser.add_argument("--json", action="store_true", help="輸出 JSON（預設格式）")
    return parser


def _load_input(source: str) -> object:
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        return json.loads(text)
    except OSError as exc:
        raise InputValidationError(f"無法讀取輸入檔：{exc}") from exc
    except UnicodeDecodeError as exc:
        raise InputValidationError(f"無法讀取輸入檔：{exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputValidationError(f"JSON 格式錯誤：{exc.msg}（第 {exc.lineno} 行）") from exc


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] not in {"solve", "generate", "-h", "--help"}:
        args_list.insert(0, "solve")
    parser = _parser()
    args = parser.parse_args(args_list)
    if args.command == "generate":
        try:
            payload = generate_puzzle(args.size, args.difficulty, args.seed)
        except InputValidationError as exc:
            print(json.dumps({"status": "INVALID_INPUT", "errors": [exc.message]}, ensure_ascii=False))
            return 2
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.command != "solve":
        parser.print_help()
        return 0

    try:
        puzzle = parse_puzzle(_load_input(args.input))
        result = solve(
            puzzle,
            SolveOptions(
                mode=args.mode,
                mark_policy=args.mark_policy,
                timeout_ms=args.timeout_ms,
                max_nodes=args.max_nodes,
            ),
        )
    except InputValidationError as exc:
        result = None
        print(json.dumps(
            {"status": "INVALID_INPUT", "uniqueness": "NOT_APPLICABLE",
             "search_complete": False, "solutions": [], "stats": {"nodes": 0, "elapsed_ms": 0},
             "errors": [exc.message], "mark_policy": args.mark_policy, "coordinate_base": 0},
            ensure_ascii=False,
        ))
        return 2
    if result is None:
        return 2
    if args.human:
        print(f"status: {result.status}")
        print(f"uniqueness: {result.uniqueness}")
        print(f"search_complete: {str(result.search_complete).lower()}")
        print("solutions (1-based row, column):")
        for solution in result.solutions:
            print("  " + ", ".join(f"({row + 1},{column + 1})"
                                    for row, column in enumerate(solution)))
        print(f"nodes: {result.nodes}; elapsed_ms: {result.elapsed_ms}")
        for error in result.errors:
            print(f"error: {error}")
    else:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    if result.status in {"TIMEOUT", "NODE_LIMIT", "CANCELLED"}:
        return 3
    if result.status == "INVALID_INPUT":
        return 2
    return 0
