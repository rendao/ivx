import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ivx.server.path_policy import canonicalize_project_path, mask_project_path, resolve_project_root


class PathPolicyTests(unittest.TestCase):
    def test_default_project_is_relative_dot(self) -> None:
        self.assertEqual(canonicalize_project_path("default", "E:/any/path", ROOT), ".")
        self.assertEqual(mask_project_path("default", "E:/any/path"), ".")

    def test_external_project_path_is_absolute_and_masked(self) -> None:
        raw = "./demo-external"
        canonical = canonicalize_project_path("project-a", raw, ROOT)
        self.assertTrue(Path(canonical).is_absolute())
        self.assertEqual(mask_project_path("project-a", canonical), "[configured, hidden]")

    def test_default_root_resolves_to_repo(self) -> None:
        resolved = resolve_project_root("default", ".", ROOT)
        self.assertEqual(resolved, ROOT.resolve())


if __name__ == "__main__":
    unittest.main()
