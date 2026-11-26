"""Prevent retired code from leaking into runtime and catch broken current docs links."""
import ast
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ("scripts/collect.py", "config/sources.json", "tests/test_collector.py")
RETIRED_OUTPUTS = ("site/data/news.json", "site/data/status.json", "site/data/sources.json")
ARCHIVE = ROOT / "archive/legacy-news/collector-v1"


class RepositoryHygieneTests(unittest.TestCase):
    def test_retired_collector_is_archived_not_live(self):
        for name in RETIRED:
            self.assertFalse((ROOT / name).exists(), name)
            self.assertTrue((ARCHIVE / name).is_file(), name)
        for name in RETIRED_OUTPUTS:
            self.assertFalse((ROOT / name).exists(), name)

    def test_runtime_does_not_import_or_invoke_retired_collector(self):
        for path in (ROOT / "scripts").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn(node.module, ("scripts.collect", "collect"), str(path))
                    if node.module == "scripts":
                        self.assertNotIn("collect", [a.name for a in node.names], str(path))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name, ("scripts.collect", "collect"), str(path))
        for path in (ROOT / ".github/workflows").glob("*.y*ml"):
            content = path.read_text(encoding="utf-8")
            for name in RETIRED:
                self.assertNotIn(name, content, str(path))
        page = (ROOT / "site/index.html").read_text(encoding="utf-8")
        for name in ("news.json", "status.json", "sources.json"):
            self.assertIsNone(re.search(r"['\"](?:data/)?" + re.escape(name) + r"['\"]", page), name)

    def test_current_documentation_links_resolve(self):
        paths = list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md"))
        paths += list((ROOT / "ops").rglob("*.md")) + list((ROOT / ".agents").rglob("*.md"))
        paths += [ROOT / "archive/README.md", ROOT / "archive/legacy-news/README.md"]
        for path in paths:
            for link in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                self.assertTrue(target.is_relative_to(ROOT), f"{path}: {link}")
                self.assertTrue(target.exists(), f"{path}: {link}")


if __name__ == "__main__":
    unittest.main()
