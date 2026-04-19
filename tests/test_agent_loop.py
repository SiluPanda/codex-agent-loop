from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent_loop.py"
spec = importlib.util.spec_from_file_location("agent_loop", SCRIPT)
agent_loop = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = agent_loop
spec.loader.exec_module(agent_loop)


@contextmanager
def temporary_directory_or_skip(testcase: unittest.TestCase):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    except (FileNotFoundError, PermissionError) as exc:
        testcase.skipTest(f"temporary directories unavailable in this environment: {exc}")


class AgentLoopTests(unittest.TestCase):
    def test_parse_budget_shorthand_minutes(self) -> None:
        self.assertEqual(agent_loop.parse_budget_shorthand("10m"), ("max_seconds", 600))

    def test_parse_budget_shorthand_turns(self) -> None:
        self.assertEqual(agent_loop.parse_budget_shorthand("5t"), ("max_turns", 5))

    def test_parse_args_supports_budget_shorthand(self) -> None:
        args = agent_loop.parse_args(["10m", "fix", "the", "tests"])
        self.assertEqual(args.max_seconds, 600)
        self.assertEqual(args.prompt, ["fix", "the", "tests"])

    def test_parse_args_supports_budget_shorthand_with_intermixed_flags(self) -> None:
        args = agent_loop.parse_args(["10m", "--approval-mode", "on-write", "fix", "the", "tests"])
        self.assertEqual(args.max_seconds, 600)
        self.assertEqual(args.approval_mode, "on-write")
        self.assertEqual(args.prompt, ["fix", "the", "tests"])

    def test_parse_args_shorthand_does_not_override_explicit_max_turns(self) -> None:
        args = agent_loop.parse_args(["--max-turns=12", "10m", "fix", "the", "tests"])
        self.assertEqual(args.max_turns, 12)
        self.assertIsNone(args.max_seconds)
        self.assertEqual(args.prompt, ["10m", "fix", "the", "tests"])

    def test_shell_command_read_only_detection(self) -> None:
        self.assertTrue(agent_loop.shell_command_is_read_only("git status"))
        self.assertTrue(agent_loop.shell_command_is_read_only("rg TODO src"))
        self.assertTrue(agent_loop.shell_command_is_read_only("rg TODO src | head"))
        self.assertFalse(agent_loop.shell_command_is_read_only("sed -i '' 's/a/b/' file.txt"))
        self.assertFalse(agent_loop.shell_command_is_read_only("sed -i.bak 's/a/b/' file.txt"))
        self.assertFalse(agent_loop.shell_command_is_read_only("awk -i inplace '{print}' file.txt"))
        self.assertFalse(agent_loop.shell_command_is_read_only("perl -pi -e 's/a/b/' file.txt"))
        self.assertFalse(agent_loop.shell_command_is_read_only("python3 script.py"))
        self.assertFalse(agent_loop.shell_command_is_read_only("echo hi > out.txt"))
        self.assertFalse(agent_loop.shell_command_is_read_only("echo $(touch should_not_run)"))
        self.assertFalse(agent_loop.shell_command_is_read_only("echo `touch should_not_run`"))
        self.assertFalse(agent_loop.shell_command_is_read_only("find . -exec rm {} \\;"))
        self.assertFalse(agent_loop.shell_command_is_read_only("git branch -D stale-branch"))

    def test_execute_shell_call_truncates_output(self) -> None:
        call = agent_loop.SimpleNamespace(
            {
                "call_id": "call-1",
                "action": {
                    "commands": ['python3 -c \'print("x" * 120)\''],
                    "max_output_length": 10,
                },
            }
        )
        output, log = agent_loop.execute_shell_call(call, Path(__file__).resolve().parents[1])
        stdout = output["output"][0]["stdout"]
        self.assertEqual(output["max_output_length"], 10)
        self.assertLessEqual(len(stdout), 10)
        self.assertEqual(stdout, log["commands"][0]["stdout"])

    def test_execute_shell_call_timeout_normalizes_bytes_for_json_logging(self) -> None:
        call = agent_loop.SimpleNamespace(
            {
                "call_id": "call-timeout",
                "action": {
                    "commands": ["sleep 5"],
                },
            }
        )
        timeout = agent_loop.subprocess.TimeoutExpired(
            cmd=["/bin/zsh", "-lc", "sleep 5"],
            timeout=0.1,
            output=b"partial stdout",
            stderr=b"partial stderr",
        )
        with mock.patch.object(agent_loop.subprocess, "run", side_effect=timeout):
            output, log = agent_loop.execute_shell_call(call, Path(__file__).resolve().parents[1])
        self.assertEqual(output["output"][0]["stdout"], "partial stdout")
        self.assertEqual(output["output"][0]["stderr"], "partial stderr")
        self.assertEqual(log["commands"][0]["stdout"], "partial stdout")
        self.assertEqual(log["commands"][0]["stderr"], "partial stderr")
        json.dumps(log)

    def test_update_diff_application(self) -> None:
        original = "def fib(n):\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)\n"
        diff = "@@\n-def fib(n):\n+def fibonacci(n):\n     if n <= 1:\n         return n\n-    return fib(n-1) + fib(n-2)\n+    return fibonacci(n-1) + fibonacci(n-2)"
        updated = agent_loop.apply_update_diff(original, diff)
        self.assertIn("def fibonacci", updated)
        self.assertIn("return fibonacci(n-1) + fibonacci(n-2)", updated)
        self.assertNotIn("return fib(n-1) + fib(n-2)", updated)

    def test_update_diff_uses_hunk_line_numbers_for_repeated_blocks(self) -> None:
        original = "A\nx\nB\nA\nx\nB\n"
        diff = "@@ -4,3 +4,3 @@\n A\n-x\n+y\n B\n"
        updated = agent_loop.apply_update_diff(original, diff)
        self.assertEqual(updated, "A\nx\nB\nA\ny\nB\n")

    def test_execute_apply_patch_preserves_crlf_line_endings(self) -> None:
        with temporary_directory_or_skip(self) as tmp:
            target = tmp / "demo.txt"
            target.write_bytes(b"a\r\nb\r\n")
            workspace_root = tmp.resolve()
            call = agent_loop.SimpleNamespace(
                {
                    "call_id": "call-update",
                    "operation": {
                        "type": "update_file",
                        "path": "demo.txt",
                        "diff": "@@\n a\n-b\n+c\n",
                    },
                }
            )
            output, log = agent_loop.execute_apply_patch(call, workspace_root)
            self.assertEqual(output["status"], "completed")
            self.assertEqual(log["status"], "completed")
            self.assertEqual(target.read_bytes(), b"a\r\nc\r\n")

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
        self.assertIn("read-only sandbox", report["backend_note"])

    def test_run_codex_exec_loop_uses_read_only_sandbox_for_on_write(self) -> None:
        with temporary_directory_or_skip(self) as run_dir:
            with mock.patch.object(agent_loop.shutil, "which", return_value="/usr/local/bin/codex"):
                with mock.patch.object(agent_loop, "has_git_repo", return_value=True):
                    with mock.patch.object(agent_loop, "collect_changed_files", return_value=[]):
                        with mock.patch.object(agent_loop.subprocess, "run") as run:
                            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                            agent_loop.run_codex_exec_loop(
                                task="inspect",
                                workspace_root=Path(__file__).resolve().parents[1],
                                run_dir=run_dir,
                                model=agent_loop.DEFAULT_MODEL,
                                reasoning_effort=agent_loop.DEFAULT_REASONING_EFFORT,
                                approval_mode="on-write",
                                max_turns=3,
                                max_seconds=60,
                            )
        cmd = run.call_args_list[0].args[0]
        self.assertIn("read-only", cmd)
        self.assertNotIn("workspace-write", cmd)

    def test_run_codex_exec_loop_uses_workspace_write_for_never(self) -> None:
        with temporary_directory_or_skip(self) as run_dir:
            with mock.patch.object(agent_loop.shutil, "which", return_value="/usr/local/bin/codex"):
                with mock.patch.object(agent_loop, "has_git_repo", return_value=True):
                    with mock.patch.object(agent_loop, "collect_changed_files", return_value=[]):
                        with mock.patch.object(agent_loop.subprocess, "run") as run:
                            run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                            agent_loop.run_codex_exec_loop(
                                task="inspect",
                                workspace_root=Path(__file__).resolve().parents[1],
                                run_dir=run_dir,
                                model=agent_loop.DEFAULT_MODEL,
                                reasoning_effort=agent_loop.DEFAULT_REASONING_EFFORT,
                                approval_mode="never",
                                max_turns=3,
                                max_seconds=60,
                            )
        cmd = run.call_args_list[0].args[0]
        self.assertIn("workspace-write", cmd)

    def test_run_codex_exec_loop_timeout_normalizes_bytes(self) -> None:
        with temporary_directory_or_skip(self) as run_dir:
            timeout = agent_loop.subprocess.TimeoutExpired(
                cmd=["codex", "exec"],
                timeout=1,
                output=b'{"type":"item.completed","item":{"type":"agent_message","text":"partial result"}}\n',
                stderr=b"timed out",
            )
            with mock.patch.object(agent_loop.shutil, "which", return_value="/usr/local/bin/codex"):
                with mock.patch.object(agent_loop, "has_git_repo", return_value=True):
                    with mock.patch.object(agent_loop, "collect_changed_files", return_value=[]):
                        with mock.patch.object(agent_loop.subprocess, "run", side_effect=timeout):
                            summary = agent_loop.run_codex_exec_loop(
                                task="inspect",
                                workspace_root=Path(__file__).resolve().parents[1],
                                run_dir=run_dir,
                                model=agent_loop.DEFAULT_MODEL,
                                reasoning_effort=agent_loop.DEFAULT_REASONING_EFFORT,
                                approval_mode="on-write",
                                max_turns=3,
                                max_seconds=1,
                            )
            stdout_text = (run_dir / "codex_exec.stdout.jsonl").read_text(encoding="utf-8")
            self.assertEqual(summary["status"], "max_time_reached")
            self.assertEqual(summary["final_answer"], "partial result")
            self.assertIn("partial result", stdout_text)

    def test_run_codex_exec_loop_surfaces_telemetry(self) -> None:
        with temporary_directory_or_skip(self) as run_dir:
            stdout = "\n".join(
                [
                    '{"type":"thread.started"}',
                    '{"type":"turn.started"}',
                    '{"type":"turn.started"}',
                    '{"type":"item.completed","item":{"type":"command_execution","command":"python3 -m unittest","status":"completed"}}',
                    '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}',
                ]
            )
            with mock.patch.object(agent_loop.shutil, "which", return_value="/usr/local/bin/codex"):
                with mock.patch.object(agent_loop, "has_git_repo", return_value=False):
                    with mock.patch.object(
                        agent_loop.subprocess,
                        "run",
                        return_value=mock.Mock(returncode=0, stdout=stdout, stderr=""),
                    ):
                        summary = agent_loop.run_codex_exec_loop(
                            task="inspect",
                            workspace_root=Path(__file__).resolve().parents[1],
                            run_dir=run_dir,
                            model=agent_loop.DEFAULT_MODEL,
                            reasoning_effort=agent_loop.DEFAULT_REASONING_EFFORT,
                            approval_mode="on-write",
                            max_turns=3,
                            max_seconds=60,
                        )
        self.assertEqual(summary["turns_used"], 2)
        self.assertEqual(summary["verification_commands"], ["python3 -m unittest"])
        self.assertEqual(summary["final_answer"], "done")

    def test_parse_git_status_porcelain_returns_changed_paths(self) -> None:
        output = " M scripts/agent_loop.py\n?? new_file.py\nR  old.py -> renamed.py\n"
        self.assertEqual(
            agent_loop.parse_git_status_porcelain(output),
            ["new_file.py", "renamed.py", "scripts/agent_loop.py"],
        )

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

    def test_task_from_args_resume_does_not_read_stdin(self) -> None:
        args = agent_loop.argparse.Namespace(
            task=None,
            prompt=[],
            resume="state.json",
            doctor=False,
            demo=False,
        )
        with mock.patch.object(agent_loop.sys, "stdin") as fake_stdin:
            fake_stdin.isatty.return_value = False
            fake_stdin.read.side_effect = AssertionError("stdin should not be read while resuming")
            task = agent_loop.task_from_args(args)
        self.assertEqual(task, "")

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
        with temporary_directory_or_skip(self) as tmp:
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

    def test_print_demo_next_steps_uses_mkdir_without_creating_tempdir(self) -> None:
        buffer = io.StringIO()
        with mock.patch.object(agent_loop, "quoted_script_command", return_value="python3 runner.py"):
            with mock.patch("sys.stdout", buffer):
                agent_loop.print_demo_next_steps()
        output = buffer.getvalue()
        self.assertIn("mkdir -p", output)
        self.assertIn("--cwd", output)

    def test_main_prints_final_backend_banner_after_fallback(self) -> None:
        backend_report = {
            "backend": "responses",
            "backend_label": "OpenAI Responses API",
            "backend_note": "initial",
            "openai_package_available": True,
            "openai_import_error": "",
            "api_key_source": "environment",
            "codex_available": True,
            "codex_path": "/usr/local/bin/codex",
            "resume_supported": True,
            "approval_mode_always_supported": True,
        }
        summary = {
            "status": "completed",
            "stop_reason": "codex_exec_fallback",
            "turns_used": 1,
            "max_turns": 8,
            "run_dir": "/tmp/run",
        }
        with temporary_directory_or_skip(self) as run_dir:
            with mock.patch.object(agent_loop, "build_backend_report", return_value=backend_report):
                with mock.patch.object(agent_loop, "ensure_openai_client", side_effect=agent_loop.LoopError("boom")):
                    with mock.patch.object(agent_loop, "create_run_dir", return_value=run_dir):
                        with mock.patch.object(agent_loop, "run_codex_exec_loop", return_value=summary):
                            with mock.patch.object(agent_loop, "print_backend_banner") as banner:
                                with mock.patch.object(agent_loop, "print_human_summary"):
                                    with mock.patch.object(agent_loop.sys, "stdin") as fake_stdin:
                                        fake_stdin.isatty.return_value = True
                                        exit_code = agent_loop.main(["--runs-dir", str(run_dir), "inspect"])
        self.assertEqual(exit_code, 0)
        printed_backend = banner.call_args.args[0]
        self.assertEqual(printed_backend["backend"], "codex-exec")
        self.assertIn("falling back to codex exec", printed_backend["backend_note"])


if __name__ == "__main__":
    unittest.main()
