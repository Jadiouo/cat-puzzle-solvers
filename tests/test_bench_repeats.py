import unittest

from bench import runner

P = {"id": "x", "n": 4, "regions": [[0, 0, 1, 1], [0, 2, 1, 1], [3, 2, 2, 1], [3, 3, 2, 2]]}
# no reference and not planted -> a clean finish is NOREF


def fake(seq):
    it = iter(seq)
    return lambda sv, p, mode, to: dict(next(it))


def ok(t):
    return {"status": "UNSAT", "solutions": [], "count": 0, "complete": True, "nodes": 1, "elapsed": t}


TO = {"status": "TIMEOUT", "solutions": [], "count": None, "complete": False, "nodes": None, "elapsed": 10.001}


class RepeatRule(unittest.TestCase):
    def test_late_timeout_makes_row_timeout(self):
        res, times, v, note = runner.run_repeats("s", P, "count", 10.0, 3, fake([ok(5.7), TO, ok(1)]))
        self.assertEqual((res["status"], v), ("TIMEOUT", "TIMEOUT"))
        self.assertEqual(len(times), 2)       # stops at the first timeout
        self.assertEqual(res["elapsed"], 10.0)
        self.assertIsNone(res["count"])

    def test_first_timeout(self):
        res, _, v, _ = runner.run_repeats("s", P, "count", 10.0, 3, fake([TO]))
        self.assertEqual((res["status"], v), ("TIMEOUT", "TIMEOUT"))

    def test_all_fine_median(self):
        res, _, v, _ = runner.run_repeats("s", P, "count", 10.0, 3, fake([ok(1), ok(3), ok(2)]))
        self.assertEqual((res["status"], v, res["elapsed"]), ("UNSAT", "NOREF", 2))

    def test_slow_but_not_killed_counts_as_timeout_with_status(self):
        res, _, v, _ = runner.run_repeats("s", P, "count", 10.0, 1, fake([ok(11.0)]))
        self.assertEqual((res["status"], v), ("TIMEOUT", "TIMEOUT"))

    def test_mismatch_outranks_timeout(self):
        bad = {"status": "SOLVED", "solutions": [[0, 0, 0, 0]], "count": 1, "complete": True, "nodes": 1, "elapsed": 1}
        res, _, v, _ = runner.run_repeats("s", P, "count", 10.0, 3, fake([bad, TO]))
        self.assertEqual(v, "MISMATCH")

    def test_count_differs_between_repeats(self):
        a, b = ok(1), dict(ok(1), count=1, status="SOLVED", solutions=[])
        _, _, v, _ = runner.run_repeats("s", P, "count", 10.0, 2, fake([a, b]))
        self.assertEqual(v, "MISMATCH")


if __name__ == "__main__":
    unittest.main()
