from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent_loop.py"
spec = importlib.util.spec_from_file_location("agent_loop", SCRIPT)
agent_loop = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = agent_loop
spec.loader.exec_module(agent_loop)


class AgentLoopTests(unittest.TestCase):
    def test_parse_budget_shorthand_minutes(self) -> None:
        self.assertEqual(agent_loop.parse_budget_shorthand("10m"), ("max_seconds", 600))

    def test_parse_budget_shorthand_turns(self) -> None:
        self.assertEqual(agent_loop.parse_budget_shorthand("5t"), ("max_turns", 5))

    def test_parse_args_supports_budget_shorthand(self) -> None:
        args = agent_loop.parse_args(["10m", "fix", "the", "tests"])
        self.assertEqual(args.max_seconds, 600)
        self.assertEqual(args.prompt, ["fix", "the", "tests"])

    def test_parse_args_shorthand_does_not_override_explicit_max_turns(self) -> None:
        args = agent_loop.parse_args(["--max-turns=12", "10m", "fix", "the", "tests"])
        self.assertEqual(args.max_turns, 12)
        self.assertIsNone(args.max_seconds)
        self.assertEqual(args.prompt, ["10m", "fix", "the", "tests"])

    def test_shell_command_read_only_detection(self) -> None:
        self.assertTrue(agent_loop.shell_command_is_read_only("git status"))
        self.assertTrue(agent_loop.shell_command_is_read_only("rg TODO src"))
        self.assertFalse(agent_loop.shell_command_is_read_only("python3 script.py"))
        self.assertFalse(agent_loop.shell_command_is_read_only("echo hi > out.txt"))

    def test_update_diff_application(self) -> None:
        original = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\n"
        diff = "@@\n-def fib(n):\n+def fibonacci(n):\n     if n <= 1:\n         return n\n-    return fib(n-1) + fib(n-2)\n+    return fibonacci(n-1) + fibonacci(n-2)"
        updated = agent_loop.apply_update_diff(original, diff)
        self.assertIn("def fibonacci", updated)
        self.assertIn("return fibonacci(n-1) + fibonacci(n-2)", updated)
        self.assertNotIn("return fib(n-1) + fib(n-2)", updated)

    def test_render_created_file_from_diff(self) -> None:
        diff = "@@\n+hello\n+world"
        created = agent_loop.render_created_file(diff)
        self.assertEqual(created, "hello\nworld")

    def test_backend_report_prefers_fallback_without_api_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(agent_loop, "read_api_key_from_auth_json", return_value=None):
                with mock.patch.object(agent_loop.shutil, "which", return_value="/usr/local/bin/codex"):
                    with mock.patch.object(agent_loop, "OpenAI", None):
                        report = agent_loop.build_backend_report()
        self.assertEqual(report["backend"], "codex-exec")
        self.assertFalse(report["resume_supported"])

    def test_task_from_args_uses_demo_default_task(self) -> None:
        args = agent_loop.argparse.Namespace(
            task=None,
            prompt=[],
            resume=None,
            doctor=False,
            demo=True,
        )
        with mock.patch.object(agent_loop.sys, "stdin") as fake_stdin:
            fake_stdin.isatty.return_value = True
            task = agent_loop.task_from_args(args)
        self.assertEqual(task, agent_loop.DEMO_TASK)

    def test_doctor_report_recommends_skill_entrypoint(self) -> None:
        backend = {
            "backend": "codex-exec",
            "backend_label": "codex exec fallback",
            "backend_note": "note",
            "openai_package_available": True,
            "openai_import_error": "",
            "api_key_source": "none",
            "codex_available": True,
            "codex_path": "/usr/local/bin/codex",
            "resume_supported": False,
            "approval_mode_always_supported": False,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            plugin_dir = tmp / "agent-loop"
            plugin_dir.mkdir()
            marketplace = tmp / "marketplace.json"
            marketplace.write_text('{"plugins":[]}')
            script_path = plugin_dir / "scripts" / "agent_loop.py"
            with mock.patch.object(agent_loop, "build_backend_report", return_value=backend):
                with mock.patch.object(agent_loop, "normalize_workspace", return_value=tmp):
                    with mock.patch.object(agent_loop, "INSTALLED_PLUGIN_DIR", plugin_dir):
                        with mock.patch.object(agent_loop, "MARKETPLACE_JSON", marketplace):
                            with mock.patch.object(agent_loop, "PLUGIN_SCRIPT", script_path):
                                with mock.patch.object(
                                    agent_loop, "marketplace_contains_plugin", return_value=True
                                ):
                                    report = agent_loop.build_doctor_report(str(tmp))
        self.assertEqual(report["codex_recommended_entrypoint"], "$agent-loop")
        self.assertIn("public Codex builds", report["codex_slash_command_note"])


if __name__ == "__main__":
    unittest.main()
