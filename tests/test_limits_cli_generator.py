import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cat_solver import SolveOptions, parse_puzzle, solve
from cat_solver.generator import generate_puzzle

ROOT = Path(__file__).resolve().parents[1]
# former private fixture replaced by the self-generated fixture (CLI tests: same assertions,
# new expected solution; (1,3)/(10,2) became (1,7)/(10,10), first/last cat 1-based).
SAMPLE = "tests/fixtures/sample10.json"


def puzzle4():
    return parse_puzzle({
        "schema_version": "1.0",
        "size": 4,
        "regions": [[f"r{row}" for _ in range(4)] for row in range(4)],
    })


class LimitTests(unittest.TestCase):
    def test_zero_nodes_is_not_unsat(self):
        result = solve(puzzle4(), SolveOptions(max_nodes=0))
        self.assertEqual((result.status, result.nodes, result.uniqueness), ("NODE_LIMIT", 0, "UNKNOWN"))
        self.assertFalse(result.search_complete)

    def test_timeout_and_partial_solution(self):
        class Clock:
            def __init__(self, threshold):
                self.calls = 0
                self.threshold = threshold

            def __call__(self):
                self.calls += 1
                return 0.0 if self.calls <= self.threshold else 1.0

        no_solution_yet = solve(
            puzzle4(), SolveOptions(timeout_ms=10, clock=Clock(1))
        )
        self.assertEqual(no_solution_yet.status, "TIMEOUT")
        self.assertEqual(no_solution_yet.uniqueness, "UNKNOWN")

        partial = solve(
            puzzle4(), SolveOptions(mode="all", max_nodes=10, timeout_ms=None)
        )
        self.assertEqual(partial.status, "NODE_LIMIT")
        self.assertEqual(len(partial.solutions), 1)
        self.assertEqual(partial.uniqueness, "UNKNOWN")
        self.assertFalse(partial.search_complete)

        timeout_after_first = solve(
            puzzle4(), SolveOptions(mode="all", timeout_ms=10, clock=Clock(10))
        )
        self.assertEqual(timeout_after_first.status, "TIMEOUT")
        self.assertEqual(len(timeout_after_first.solutions), 1)
        self.assertEqual(timeout_after_first.uniqueness, "UNKNOWN")
        self.assertFalse(timeout_after_first.search_complete)

    def test_cancelled_and_multiple_before_abort(self):
        cancelled = solve(puzzle4(), SolveOptions(cancel_check=lambda: True))
        self.assertEqual((cancelled.status, cancelled.search_complete), ("CANCELLED", False))
        limited = solve(puzzle4(), SolveOptions(mode="all", max_nodes=13, timeout_ms=None))
        self.assertEqual(limited.status, "NODE_LIMIT")
        self.assertGreaterEqual(len(limited.solutions), 2)
        self.assertEqual(limited.uniqueness, "MULTIPLE")


class CliTests(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run(
            [sys.executable, "-m", "cat_solver", *args],
            cwd=ROOT,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_json_cli_and_legacy_invocation(self):
        output = self.run_cli("solve", SAMPLE, "--mode", "classify")
        self.assertEqual(output.returncode, 0, output.stderr)
        result = json.loads(output.stdout)
        self.assertEqual(result["coordinate_base"], 0)
        self.assertEqual(result["uniqueness"], "UNIQUE")
        self.assertEqual(result["solutions"][0], [6, 1, 5, 0, 3, 7, 2, 8, 4, 9])
        old_form = self.run_cli(SAMPLE, "--mode", "classify")
        self.assertEqual(json.loads(old_form.stdout)["status"], "SOLVED")

    def test_invalid_json_and_missing_file_exit_codes(self):
        malformed = self.run_cli("solve", "-", input_text="{bad")
        self.assertEqual(malformed.returncode, 2)
        self.assertEqual(json.loads(malformed.stdout)["status"], "INVALID_INPUT")
        missing = self.run_cli("solve", "does-not-exist.json")
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(json.loads(missing.stdout)["status"], "INVALID_INPUT")
        self.assertNotIn("Traceback", missing.stdout + missing.stderr)

    def test_invalid_utf8_file_is_reported_as_invalid_input(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            input_path = Path(directory) / "invalid-utf8.json"
            input_path.write_bytes(b"\xff")
            output = self.run_cli("solve", str(input_path))

        self.assertEqual(output.returncode, 2)
        result = json.loads(output.stdout)
        self.assertEqual(result["status"], "INVALID_INPUT")
        self.assertEqual(result["uniqueness"], "NOT_APPLICABLE")
        self.assertNotIn("Traceback", output.stdout + output.stderr)

    def test_human_output_is_one_based(self):
        output = self.run_cli("solve", SAMPLE, "--human", "--mode", "first")
        self.assertEqual(output.returncode, 0)
        self.assertIn("(1,7)", output.stdout)
        self.assertIn("(10,10)", output.stdout)

    def test_generate_then_solve_multiple_sizes_and_difficulties(self):
        for size, difficulty, seed in ((1, "easy", 12), (4, "medium", 22), (7, "hard", 32), (10, "easy", 42)):
            with self.subTest(size=size, difficulty=difficulty):
                generated = self.run_cli(
                    "generate", "--size", str(size), "--difficulty", difficulty, "--seed", str(seed)
                )
                self.assertEqual(generated.returncode, 0, generated.stderr)
                payload = json.loads(generated.stdout)
                self.assertEqual(payload["generator"], {"difficulty": difficulty, "seed": seed})
                solved = self.run_cli("solve", "-", input_text=generated.stdout)
                self.assertEqual(solved.returncode, 0, solved.stderr)
                result = json.loads(solved.stdout)
                self.assertEqual((result["status"], result["uniqueness"]), ("SOLVED", "UNIQUE"))
                self.assertTrue(result["search_complete"])

    def test_generator_reproducibility_and_bad_sizes(self):
        self.assertEqual(generate_puzzle(7, "hard", 123), generate_puzzle(7, "hard", 123))
        self.assertNotEqual(generate_puzzle(7, "hard", 123), generate_puzzle(7, "hard", 124))
        for size in (2, 3):
            result = self.run_cli("generate", "--size", str(size), "--seed", "1")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["status"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
