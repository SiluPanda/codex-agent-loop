from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install.py"
spec = importlib.util.spec_from_file_location("install_script", SCRIPT)
install_script = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = install_script
spec.loader.exec_module(install_script)


class InstallScriptTests(unittest.TestCase):
    def test_merge_plugin_entry_appends_when_missing(self) -> None:
        document = {"name": "local", "interface": {"displayName": "Local"}, "plugins": []}
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "codex-agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertEqual(len(merged["plugins"]), 1)
        self.assertEqual(merged["plugins"][0]["name"], "codex-agent-loop")

    def test_merge_plugin_entry_replaces_existing(self) -> None:
        document = {
            "name": "local",
            "interface": {"displayName": "Local"},
            "plugins": [{"name": "codex-agent-loop", "category": "Old"}],
        }
        entry = install_script.plugin_entry(Path.home() / ".codex" / "plugins" / "codex-agent-loop")
        merged = install_script.merge_plugin_entry(document, entry)
        self.assertEqual(len(merged["plugins"]), 1)
        self.assertEqual(merged["plugins"][0]["category"], "Coding")


if __name__ == "__main__":
    unittest.main()
