from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install.py"
spec = importlib.util.spec_from_file_location("install_script", SCRIPT)
install_script = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = install_script
spec.loader.exec_module(install_script)


@contextmanager
def temporary_directory_or_skip(testcase: unittest.TestCase):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    except (FileNotFoundError, PermissionError) as exc:
        testcase.skipTest(f"temporary directories unavailable in this environment: {exc}")


class InstallScriptTests(unittest.TestCase):
    def test_load_marketplace_accepts_list_root(self) -> None:
        with temporary_directory_or_skip(self) as tmpdir:
            path = tmpdir / "marketplace.json"
            path.write_text(json.dumps([{"name": "local-plugins", "plugins": []}]))
            document = install_script.load_marketplace(path)
        self.assertIsInstance(document, list)
        self.assertEqual(document[0]["name"], "local-plugins")

    def test_merge_plugin_entry_appends_when_missing(self) -> None:
        document = {"name": "local", "interface": {"displayName": "Local"}, "plugins": []}
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertEqual(len(merged["plugins"]), 1)
        self.assertEqual(merged["plugins"][0]["name"], "agent-loop")

    def test_merge_plugin_entry_replaces_legacy_existing(self) -> None:
        document = {
            "name": "local",
            "interface": {"displayName": "Local"},
            "plugins": [{"name": "codex-agent-loop", "category": "Old"}],
        }
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertEqual(len(merged["plugins"]), 1)
        self.assertEqual(merged["plugins"][0]["category"], "Coding")
        self.assertEqual(merged["plugins"][0]["name"], "agent-loop")

    def test_merge_plugin_entry_dedupes_current_and_legacy_entries(self) -> None:
        document = {
            "name": "local",
            "interface": {"displayName": "Local"},
            "plugins": [
                {"name": "codex-agent-loop", "category": "Old"},
                {"name": "agent-loop", "category": "Older"},
            ],
        }
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertEqual(len(merged["plugins"]), 1)
        self.assertEqual(merged["plugins"][0]["name"], "agent-loop")

    def test_merge_plugin_entry_appends_local_plugins_document_for_list_root(self) -> None:
        document = [{"name": "team-plugins", "plugins": [{"name": "other-plugin"}]}]
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertIsInstance(merged, list)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[-1]["name"], "local-plugins")
        self.assertEqual(merged[-1]["plugins"][0]["name"], "agent-loop")


if __name__ == "__main__":
    unittest.main()
