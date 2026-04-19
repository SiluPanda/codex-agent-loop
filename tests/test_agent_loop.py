from __future__ import annotations

import importlib.util
import os
import sys
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


if __name__ == "__main__":
    unittest.main()
