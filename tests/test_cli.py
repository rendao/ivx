import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx import cli


class CliTests(unittest.TestCase):
    def test_help_returns_zero(self) -> None:
        old_argv = sys.argv
        try:
            sys.argv = ["ivx", "--help"]
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = cli.main()
            self.assertEqual(code, 0)
            self.assertIn("Usage:", buffer.getvalue())
        finally:
            sys.argv = old_argv

    def test_unknown_command_returns_two(self) -> None:
        old_argv = sys.argv
        try:
            sys.argv = ["ivx", "unknown-command"]
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = cli.main()
            self.assertEqual(code, 2)
            self.assertIn("Unknown command", buffer.getvalue())
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
