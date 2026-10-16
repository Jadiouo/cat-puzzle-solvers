"""Unit tests for the pure drag helpers in docs/js/drag.js (mode choice, cell interpolation, undo history)
and the Play-mode state transitions in docs/js/game.js (gold/red judging, locking, undo, hint, completion).
Skipped when node is missing. Run: python3 -m unittest tests.test_demo_drag -v"""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(shutil.which("node"), "node not installed")
class DragJs(unittest.TestCase):
    def test_drag_helpers(self):
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "js", "verify_drag.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_game_state_transitions(self):
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "js", "verify_game.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
