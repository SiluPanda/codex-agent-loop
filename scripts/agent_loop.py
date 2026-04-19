#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover - import guard
    OpenAI = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_TURNS = 8
DEFAULT_APPROVAL_MODE = "on-write"
APPROVAL_MODES = ("never", "on-write", "always")
REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
RUNS_DIR = Path.home() / ".codex" / "agent-loop" / "runs"
AUTH_JSON = Path.home() / ".codex" / "auth.json"
MARKETPLACE_JSON = Path.home() / ".agents" / "plugins" / "marketplace.json"
INSTALLED_PLUGIN_DIR = Path.home() / ".codex" / "plugins" / "codex-agent-loop"
PLUGIN_SCRIPT = Path(__file__).resolve()
PLUGIN_ROOT = PLUGIN_SCRIPT.parents[1]
DOCTOR_SCHEMA_VERSION = 1
DEMO_TASK = "Inspect this workspace and report what files exist. Do not modify anything."

SAFE_COMMANDS = {
    "pwd",
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "stat",
    "file",
    "find",
    "grep",
    "rg",
    "sed",
    "awk",
    "cut",
    "sort",
    "uniq",
    "tr",
    "which",
    "whereis",
    "realpath",
    "readlink",
    "env",
    "printenv",
    "echo",
    "tree",
    "du",
    "df",
    "ps",
    "id",
    "uname",
    "date",
}
SAFE_GIT_SUBCOMMANDS = {
    "status",
    "diff",
    "log",
    "show",
    "rev-parse",
    "branch",
    "ls-files",
    "grep",
}
WRITE_HINTS = (
    ">",
    ">>",
    "| tee",
    " rm ",
    " mv ",
    " cp ",
    " mkdir ",
    " touch ",
    " chmod ",
    " chown ",
    " ln ",
    " patch ",
    " git apply",
    " git checkout",
    " git switch",
    " git reset",
    " git clean",
    " git commit",
    " git add",
    " npm install",
    " pnpm install",
    " yarn install",
    " pip install",
    " poetry add",
    " cargo add",
)


class LoopError(RuntimeError):
    pass


class ApprovalPause(SystemExit):
    def __init__(self, state_path: Path):
        super().__init__(2)
        self.state_path = state_path


@dataclass
class PatchHunk:
    before: list[str]
    after: list[str]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded, resumable coding loop with OpenAI Responses shell/apply_patch tools."
    )
    parser.add_argument("prompt", nargs="*", help="Task prompt when --task is not used.")
    parser.add_argument("--task", help="Task prompt.")
    parser.add_argument("--resume", help="Resume from a saved state.json file.")
    parser.add_argument(
        "--approve-pending",
        action="store_true",
        help="Approve and execute the pending tool calls stored in --resume once.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Diagnose auth, backend, install, and marketplace status without running a task.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run a guided first-run demo using a safe read-only inspection task.",
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        choices=REASONING_EFFORTS,
        default=DEFAULT_REASONING_EFFORT,
    )
    parser.add_argument(
        "--approval-mode",
        choices=APPROVAL_MODES,
        default=DEFAULT_APPROVAL_MODE,
    )
    parser.add_argument(
        "--cwd",
        default=os.getcwd(),
        help="Workspace root for shell commands and patch paths (default: current directory).",
    )
    parser.add_argument(
        "--runs-dir",
        default=str(RUNS_DIR),
        help="Directory for logs and resumable state.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human-oriented summary.",
    )
    args = parser.parse_args(argv)
    if args.max_turns < 1:
        parser.error("--max-turns must be >= 1")
    if args.doctor and (args.resume or args.approve_pending):
        parser.error("--doctor cannot be combined with --resume or --approve-pending")
    return args


def ensure_openai_client() -> OpenAI:
    if OpenAI is None:
        raise LoopError(f"openai package import failed: {IMPORT_ERROR}")

    api_key = os.environ.get("OPENAI_API_KEY") or read_api_key_from_auth_json()
    if not api_key:
        raise LoopError(
            "No OPENAI_API_KEY found. Set OPENAI_API_KEY or ensure ~/.codex/auth.json contains one."
        )
    return OpenAI(api_key=api_key)


def read_api_key_from_auth_json() -> str | None:
    if not AUTH_JSON.exists():
        return None
    try:
        data = json.loads(AUTH_JSON.read_text())
    except Exception:
        return None
    value = data.get("OPENAI_API_KEY")
    return value if isinstance(value, str) and value else None


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def now_ts() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def normalize_workspace(path: str) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.exists():
        raise LoopError(f"Workspace root does not exist: {root}")
    if not root.is_dir():
        raise LoopError(f"Workspace root is not a directory: {root}")
    return root


def build_demo_task() -> str:
    return DEMO_TASK


def task_from_args(args: argparse.Namespace) -> str:
    if args.doctor:
        return ""

    parts: list[str] = []
    if args.task:
        parts.append(args.task)
    if args.prompt:
        parts.append(" ".join(args.prompt).strip())
    if not sys.stdin.isatty():
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            parts.append(stdin_text)
    task = "\n".join(part for part in parts if part).strip()
    if not task and args.demo:
        return build_demo_task()
    if not task and not args.resume:
        raise LoopError("Provide a task via --task, positional prompt text, stdin, or --resume.")
    return task


def developer_instructions(workspace_root: Path, max_turns: int, approval_mode: str) -> str:
    return textwrap.dedent(
        f"""
        You are Codex Agent Loop, a persistent coding agent.

        Workspace root: {workspace_root}
        Max loop turns: {max_turns}
        Approval mode: {approval_mode}

        Rules:
        - Persist until the task is complete, you hit the turn cap, or the host pauses for approval.
        - Use shell to inspect the workspace, run tests, and validate changes.
        - Use apply_patch to edit files when edits are necessary.
        - Never claim a command ran or a file changed unless you emitted the corresponding tool call.
        - Verify important changes before concluding.
        - Do not promise future background work or deferred tool calls.
        - Prefer small, targeted edits and concise final summaries.
        - If you are blocked, explain the exact blocker and the next best action.
        """
    ).strip()


def serialize_model(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return value.model_dump()
    if isinstance(value, list):
        return [serialize_model(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_model(v) for k, v in value.items()}
    return value


def response_output_text(response: Any) -> str:
    texts: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for part in getattr(item, "content", []) or []:
            if getattr(part, "type", None) == "output_text":
                text = getattr(part, "text", "")
                if text:
                    texts.append(text)
    return "\n".join(texts).strip()


def response_tool_calls(response: Any) -> list[Any]:
    calls: list[Any] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) in {"shell_call", "apply_patch_call"}:
            calls.append(item)
    return calls


def shell_command_is_read_only(command: str) -> bool:
    normalized = f" {command.strip()} "
    for hint in WRITE_HINTS:
        if hint in normalized:
            return False
    try:
        parts = shlex.split(command, posix=True)
    except Exception:
        return False
    if not parts:
        return True
    cmd = parts[0]
    if cmd == "git":
        return len(parts) >= 2 and parts[1] in SAFE_GIT_SUBCOMMANDS
    return cmd in SAFE_COMMANDS


def shell_call_is_read_only(commands: Iterable[str]) -> bool:
    return all(shell_command_is_read_only(cmd) for cmd in commands)


def needs_approval(call: Any, approval_mode: str) -> bool:
    if approval_mode == "never":
        return False
    if getattr(call, "type", None) == "apply_patch_call":
        return True
    if approval_mode == "always":
        return True
    if getattr(call, "type", None) == "shell_call":
        commands = list(getattr(getattr(call, "action", None), "commands", []) or [])
        return not shell_call_is_read_only(commands)
    return False


def safe_workspace_path(workspace_root: Path, relative_path: str) -> Path:
    candidate = (workspace_root / relative_path).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise LoopError(f"Patch path escapes workspace root: {relative_path}") from exc
    return candidate


def parse_headerless_hunks(diff_text: str) -> list[PatchHunk]:
    lines = diff_text.replace("\r\n", "\n").split("\n")
    hunks: list[PatchHunk] = []
    current_before: list[str] | None = None
    current_after: list[str] | None = None

    for line in lines:
        if line.startswith(("--- ", "+++ ")) or line == "\\ No newline at end of file":
            continue
        if line.startswith("@@"):
            if current_before is not None:
                hunks.append(PatchHunk(current_before, current_after or []))
            current_before = []
            current_after = []
            continue
        if line and line[0] in {" ", "+", "-"}:
            if current_before is None:
                current_before = []
                current_after = []
            prefix, content = line[0], line[1:]
            if prefix in {" ", "-"}:
                current_before.append(content)
            if prefix in {" ", "+"}:
                current_after.append(content)
            continue
        if line == "":
            continue

    if current_before is not None:
        hunks.append(PatchHunk(current_before, current_after or []))
    return hunks


def find_subsequence(haystack: list[str], needle: list[str], start: int = 0) -> int | None:
    if not needle:
        return start
    end = len(haystack) - len(needle) + 1
    for idx in range(max(start, 0), max(end, 0)):
        if haystack[idx : idx + len(needle)] == needle:
            return idx
    return None


def apply_update_diff(original_text: str, diff_text: str) -> str:
    hunks = parse_headerless_hunks(diff_text)
    if not hunks:
        raise LoopError("Could not parse update_file diff into hunks.")

    lines = original_text.replace("\r\n", "\n").split("\n")
    original_had_trailing_newline = original_text.endswith("\n")
    cursor = 0

    for hunk in hunks:
        idx = find_subsequence(lines, hunk.before, cursor)
        if idx is None:
            idx = find_subsequence(lines, hunk.before, 0)
        if idx is None:
            preview = "\\n".join(hunk.before[:8])
            raise LoopError(f"Failed to apply patch hunk. Could not match:\n{preview}")
        end = idx + len(hunk.before)
        lines[idx:end] = hunk.after
        cursor = idx + len(hunk.after)

    rendered = "\n".join(lines)
    if original_had_trailing_newline and rendered and not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def render_created_file(diff_text: str) -> str:
    hunks = parse_headerless_hunks(diff_text)
    if hunks:
        content_lines: list[str] = []
        for hunk in hunks:
            content_lines.extend(hunk.after)
        rendered = "\n".join(content_lines)
        if diff_text.endswith("\n") and rendered and not rendered.endswith("\n"):
            rendered += "\n"
        return rendered
    return diff_text


def execute_apply_patch(call: Any, workspace_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    operation = getattr(call, "operation")
    op_type = getattr(operation, "type")
    rel_path = getattr(operation, "path")
    target = safe_workspace_path(workspace_root, rel_path)

    if op_type == "delete_file":
        if not target.exists():
            raise LoopError(f"delete_file target does not exist: {rel_path}")
        target.unlink()
        log = {"tool": "apply_patch", "operation": op_type, "path": rel_path, "status": "completed"}
        output = {
            "type": "apply_patch_call_output",
            "call_id": call.call_id,
            "status": "completed",
            "output": f"Deleted {rel_path}",
        }
        return output, log

    diff_text = getattr(operation, "diff", "")
    target.parent.mkdir(parents=True, exist_ok=True)

    if op_type == "create_file":
        if target.exists():
            raise LoopError(f"create_file target already exists: {rel_path}")
        rendered = render_created_file(diff_text)
        target.write_text(rendered, encoding="utf-8")
        log = {"tool": "apply_patch", "operation": op_type, "path": rel_path, "status": "completed"}
        output = {
            "type": "apply_patch_call_output",
            "call_id": call.call_id,
            "status": "completed",
            "output": f"Created {rel_path}",
        }
        return output, log

    if op_type == "update_file":
        if not target.exists():
            raise LoopError(f"update_file target does not exist: {rel_path}")
        original = target.read_text(encoding="utf-8")
        rendered = apply_update_diff(original, diff_text)
        target.write_text(rendered, encoding="utf-8")
        log = {"tool": "apply_patch", "operation": op_type, "path": rel_path, "status": "completed"}
        output = {
            "type": "apply_patch_call_output",
            "call_id": call.call_id,
            "status": "completed",
            "output": f"Updated {rel_path}",
        }
        return output, log

    raise LoopError(f"Unsupported apply_patch operation type: {op_type}")


def execute_shell_call(call: Any, workspace_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    commands = list(getattr(getattr(call, "action", None), "commands", []) or [])
    timeout_ms = getattr(getattr(call, "action", None), "timeout_ms", None) or 120000
    max_output_length = getattr(getattr(call, "action", None), "max_output_length", None)

    outputs: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    for command in commands:
        try:
            proc = subprocess.run(
                ["/bin/zsh", "-lc", command],
                cwd=str(workspace_root),
                env=os.environ.copy(),
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            outcome = {"type": "exit", "exit_code": int(proc.returncode)}
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            outcome = {"type": "timeout"}

        outputs.append({"stdout": stdout, "stderr": stderr, "outcome": outcome})
        executed.append({"command": command, "stdout": stdout, "stderr": stderr, "outcome": outcome})

    payload: dict[str, Any] = {
        "type": "shell_call_output",
        "call_id": call.call_id,
        "output": outputs,
    }
    if max_output_length is not None:
        payload["max_output_length"] = int(max_output_length)

    log = {
        "tool": "shell",
        "status": "completed",
        "commands": executed,
        "read_only": shell_call_is_read_only(commands),
    }
    return payload, log


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def quoted_script_command() -> str:
    return f"python3 {shlex.quote(str(PLUGIN_SCRIPT))}"


def print_pause_message(state_path: Path, pending_calls: list[dict[str, Any]]) -> None:
    print("\nLoop paused for approval.")
    print(f"State file: {state_path}")
    for call in pending_calls:
        if call.get("type") == "apply_patch_call":
            op = call.get("operation", {})
            print(f"- Pending patch: {op.get('type')} {op.get('path')}")
        elif call.get("type") == "shell_call":
            commands = call.get("action", {}).get("commands", [])
            print("- Pending shell commands:")
            for command in commands:
                print(f"  - {command}")
    print("Resume with: " f"{quoted_script_command()} --resume {shlex.quote(str(state_path))} --approve-pending")


def build_initial_input(task: str, workspace_root: Path, approval_mode: str, max_turns: int) -> str:
    return textwrap.dedent(
        f"""
        Workspace root: {workspace_root}
        Approval mode: {approval_mode}
        Max turns: {max_turns}

        Task:
        {task}
        """
    ).strip()


def backend_label(backend: str) -> str:
    if backend == "responses":
        return "OpenAI Responses API"
    if backend == "codex-exec":
        return "codex exec fallback"
    return backend


def find_api_key_source() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return "environment"
    if read_api_key_from_auth_json():
        return "~/.codex/auth.json"
    return "none"


def has_git_repo(workspace_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def marketplace_contains_plugin(path: Path = MARKETPLACE_JSON) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except Exception:
        return False

    if isinstance(data, dict):
        plugins = data.get("plugins", [])
        return isinstance(plugins, list) and any(
            isinstance(plugin, dict) and plugin.get("name") == "codex-agent-loop" for plugin in plugins
        )
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            plugins = item.get("plugins", [])
            if isinstance(plugins, list) and any(
                isinstance(plugin, dict) and plugin.get("name") == "codex-agent-loop" for plugin in plugins
            ):
                return True
    return False


def path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def build_backend_report() -> dict[str, Any]:
    api_key_source = find_api_key_source()
    codex_path = shutil.which("codex")
    openai_package_available = OpenAI is not None

    if openai_package_available and api_key_source != "none":
        backend = "responses"
    elif codex_path:
        backend = "codex-exec"
    else:
        backend = "unavailable"

    report = {
        "backend": backend,
        "backend_label": backend_label(backend),
        "openai_package_available": openai_package_available,
        "openai_import_error": str(IMPORT_ERROR) if IMPORT_ERROR else "",
        "api_key_source": api_key_source,
        "codex_available": bool(codex_path),
        "codex_path": codex_path or "",
        "resume_supported": backend == "responses",
        "approval_mode_always_supported": backend == "responses",
        "backend_note": "",
    }
    if backend == "responses":
        report["backend_note"] = f"Using OpenAI Responses API because an API key was found in {api_key_source}."
    elif backend == "codex-exec":
        report["backend_note"] = (
            "Using codex exec fallback because no OPENAI_API_KEY was found. "
            "Resume/approval state and approval_mode=always are unavailable in this mode."
        )
    else:
        report["backend_note"] = (
            "No usable backend found. Install Codex or set OPENAI_API_KEY, then re-run --doctor."
        )
    return report


def build_doctor_report(cwd: str) -> dict[str, Any]:
    backend = build_backend_report()
    try:
        workspace_root = normalize_workspace(cwd)
        workspace_error = ""
    except Exception as exc:
        workspace_root = Path(cwd).expanduser().resolve()
        workspace_error = str(exc)

    installed_plugin_present = INSTALLED_PLUGIN_DIR.exists()
    marketplace_present = MARKETPLACE_JSON.exists()
    marketplace_has_plugin = marketplace_contains_plugin(MARKETPLACE_JSON)

    if backend["backend"] == "unavailable":
        next_step = "Set OPENAI_API_KEY or install Codex, then re-run --doctor."
    elif not installed_plugin_present or not marketplace_has_plugin:
        next_step = f"python3 {shlex.quote(str(PLUGIN_ROOT / 'scripts' / 'install.py'))}"
    else:
        next_step = f"{quoted_script_command()} --demo"

    return {
        "schema_version": DOCTOR_SCHEMA_VERSION,
        "generated_at": now_ts(),
        "workspace_root": str(workspace_root),
        "workspace_error": workspace_error,
        "current_script_path": str(PLUGIN_SCRIPT),
        "current_script_is_installed_copy": path_is_within(PLUGIN_SCRIPT, INSTALLED_PLUGIN_DIR),
        "installed_plugin_path": str(INSTALLED_PLUGIN_DIR),
        "installed_plugin_present": installed_plugin_present,
        "marketplace_path": str(MARKETPLACE_JSON),
        "marketplace_present": marketplace_present,
        "marketplace_contains_plugin": marketplace_has_plugin,
        "backend": backend["backend"],
        "backend_label": backend["backend_label"],
        "backend_note": backend["backend_note"],
        "openai_package_available": backend["openai_package_available"],
        "openai_import_error": backend["openai_import_error"],
        "api_key_source": backend["api_key_source"],
        "codex_available": backend["codex_available"],
        "codex_path": backend["codex_path"],
        "resume_supported": backend["resume_supported"],
        "approval_mode_always_supported": backend["approval_mode_always_supported"],
        "recommended_next_step": next_step,
    }


def print_doctor_report(report: dict[str, Any]) -> None:
    print("Codex Agent Loop doctor")
    print(f"Workspace: {report['workspace_root']}")
    if report.get("workspace_error"):
        print(f"Workspace check: {report['workspace_error']}")
    print(f"Current script: {report['current_script_path']}")
    print(
        "Installed plugin copy: "
        f"{'yes' if report['installed_plugin_present'] else 'no'} ({report['installed_plugin_path']})"
    )
    print(
        "Marketplace entry: "
        f"{'yes' if report['marketplace_contains_plugin'] else 'no'} ({report['marketplace_path']})"
    )
    print(f"Codex executable: {'yes' if report['codex_available'] else 'no'}")
    print(f"OpenAI Python package: {'yes' if report['openai_package_available'] else 'no'}")
    if report.get("openai_import_error"):
        print(f"OpenAI import error: {report['openai_import_error']}")
    api_key_source = report.get("api_key_source", "none")
    print(f"API key source: {api_key_source if api_key_source != 'none' else 'not found'}")
    print(f"Selected backend: {report['backend_label']}")
    print(f"Resume approvals: {'supported' if report['resume_supported'] else 'unavailable'}")
    print(
        "approval_mode=always: "
        f"{'supported' if report['approval_mode_always_supported'] else 'unavailable'}"
    )
    print(f"Note: {report['backend_note']}")
    print(f"Next step: {report['recommended_next_step']}")


def print_backend_banner(report: dict[str, Any]) -> None:
    print(f"Backend: {report['backend_label']}")
    if report["backend"] == "responses":
        print(f"Auth: API key from {report['api_key_source']}")
    elif report["backend"] == "codex-exec":
        print("Auth: local Codex login fallback (no OPENAI_API_KEY found)")
        print("Limits: resume approvals unavailable; approval_mode=always unavailable.")
    print()


def run_loop(
    client: OpenAI,
    *,
    task: str,
    workspace_root: Path,
    run_dir: Path,
    model: str,
    reasoning_effort: str,
    approval_mode: str,
    max_turns: int,
    resume_state: dict[str, Any] | None = None,
    approve_pending: bool = False,
) -> dict[str, Any]:
    tools = [
        {"type": "shell", "environment": {"type": "local"}},
        {"type": "apply_patch"},
    ]
    instructions = developer_instructions(workspace_root, max_turns, approval_mode)
    responses_jsonl = run_dir / "responses.jsonl"
    events_jsonl = run_dir / "events.jsonl"
    state_path = run_dir / "state.json"

    last_text = resume_state.get("last_response_excerpt", "") if resume_state else ""
    changed_paths: list[str] = list(resume_state.get("files_changed", [])) if resume_state else []
    verification_commands: list[str] = list(resume_state.get("verification_commands", [])) if resume_state else []

    if resume_state:
        previous_response_id = resume_state["previous_response_id"]
        turns_used = int(resume_state.get("turns_used", 0))
        initial_task = resume_state.get("task", task)
        pending_calls = resume_state.get("pending_calls", [])
        if pending_calls and not approve_pending:
            print_pause_message(state_path, pending_calls)
            raise ApprovalPause(state_path)
        input_items: list[dict[str, Any]] = []
        for call in pending_calls:
            call_type = call.get("type")
            if call_type == "shell_call":
                shell_output, log = execute_shell_call(SimpleNamespace(call), workspace_root)
                input_items.append(shell_output)
                append_jsonl(events_jsonl, {"ts": now_ts(), **log})
                for cmd in log.get("commands", []):
                    verification_commands.append(cmd["command"])
            elif call_type == "apply_patch_call":
                try:
                    patch_output, log = execute_apply_patch(SimpleNamespace(call), workspace_root)
                except Exception as exc:
                    patch_output = {
                        "type": "apply_patch_call_output",
                        "call_id": call["call_id"],
                        "status": "failed",
                        "output": str(exc),
                    }
                    log = {
                        "tool": "apply_patch",
                        "status": "failed",
                        "path": call.get("operation", {}).get("path"),
                        "error": str(exc),
                    }
                input_items.append(patch_output)
                append_jsonl(events_jsonl, {"ts": now_ts(), **log})
                path = log.get("path")
                if path and log.get("status") == "completed":
                    changed_paths.append(path)
            else:
                raise LoopError(f"Unsupported pending call type in resume state: {call_type}")
    else:
        previous_response_id = None
        turns_used = 0
        initial_task = task
        input_items = [build_initial_input(task, workspace_root, approval_mode, max_turns)]

    while turns_used < max_turns:
        turns_used += 1
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=input_items,
            previous_response_id=previous_response_id,
            tools=tools,
            parallel_tool_calls=False,
            reasoning={"effort": reasoning_effort},
            metadata={"runner": "codex-agent-loop", "turn": str(turns_used)},
        )
        response_payload = serialize_model(response)
        append_jsonl(responses_jsonl, response_payload)
        last_text = response_output_text(response) or last_text
        previous_response_id = getattr(response, "id")
        calls = response_tool_calls(response)

        if not calls:
            summary = {
                "status": "completed",
                "stop_reason": "completed",
                "backend": "responses",
                "run_dir": str(run_dir),
                "state_path": str(state_path),
                "turns_used": turns_used,
                "max_turns": max_turns,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "approval_mode": approval_mode,
                "workspace_root": str(workspace_root),
                "task": initial_task,
                "files_changed": sorted(set(changed_paths)),
                "verification_commands": verification_commands,
                "final_answer": last_text,
            }
            write_state(state_path, {**summary, "updated_at": now_ts()})
            return summary

        pending = [serialize_model(call) for call in calls if needs_approval(call, approval_mode)]
        if pending:
            state = {
                "schema_version": 1,
                "status": "paused_for_approval",
                "backend": "responses",
                "updated_at": now_ts(),
                "run_dir": str(run_dir),
                "state_path": str(state_path),
                "workspace_root": str(workspace_root),
                "task": initial_task,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "approval_mode": approval_mode,
                "max_turns": max_turns,
                "turns_used": turns_used,
                "previous_response_id": previous_response_id,
                "last_response_excerpt": last_text,
                "files_changed": sorted(set(changed_paths)),
                "verification_commands": verification_commands,
                "pending_calls": pending,
            }
            write_state(state_path, state)
            print_pause_message(state_path, pending)
            raise ApprovalPause(state_path)

        input_items = []
        for call in calls:
            if getattr(call, "type", None) == "shell_call":
                shell_output, log = execute_shell_call(call, workspace_root)
                append_jsonl(events_jsonl, {"ts": now_ts(), **log})
                input_items.append(shell_output)
                for cmd in log.get("commands", []):
                    verification_commands.append(cmd["command"])
            elif getattr(call, "type", None) == "apply_patch_call":
                try:
                    patch_output, log = execute_apply_patch(call, workspace_root)
                except Exception as exc:
                    patch_output = {
                        "type": "apply_patch_call_output",
                        "call_id": call.call_id,
                        "status": "failed",
                        "output": str(exc),
                    }
                    log = {
                        "tool": "apply_patch",
                        "status": "failed",
                        "path": getattr(getattr(call, "operation", None), "path", None),
                        "error": str(exc),
                    }
                append_jsonl(events_jsonl, {"ts": now_ts(), **log})
                input_items.append(patch_output)
                path = log.get("path")
                if path and log.get("status") == "completed":
                    changed_paths.append(path)
            else:
                raise LoopError(f"Unsupported tool call type: {getattr(call, 'type', None)}")

    summary = {
        "status": "max_turns_reached",
        "stop_reason": "max_turns_reached",
        "backend": "responses",
        "run_dir": str(run_dir),
        "state_path": str(state_path),
        "turns_used": turns_used,
        "max_turns": max_turns,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "approval_mode": approval_mode,
        "workspace_root": str(workspace_root),
        "task": initial_task,
        "files_changed": sorted(set(changed_paths)),
        "verification_commands": verification_commands,
        "final_answer": last_text,
    }
    write_state(state_path, {**summary, "updated_at": now_ts()})
    return summary


class SimpleNamespace:
    def __init__(self, data: dict[str, Any]):
        self.__dict__.update(data)
        if isinstance(getattr(self, "action", None), dict):
            self.action = SimpleNamespace(self.action)
        if isinstance(getattr(self, "operation", None), dict):
            self.operation = SimpleNamespace(self.operation)


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"Status: {summary['status']}")
    print(f"Stop reason: {summary['stop_reason']}")
    print(f"Turns used: {summary['turns_used']}/{summary['max_turns']}")
    print(f"Run dir: {summary['run_dir']}")
    if summary.get("files_changed"):
        print("Files changed:")
        for path in summary["files_changed"]:
            print(f"- {path}")
    if summary.get("verification_commands"):
        print("Verification commands:")
        for cmd in summary["verification_commands"][-10:]:
            print(f"- {cmd}")
    if summary.get("final_answer"):
        print("\nFinal answer:\n")
        print(summary["final_answer"])


def create_run_dir(runs_dir: Path) -> Path:
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def build_codex_exec_prompt(task: str, workspace_root: Path, max_turns: int, approval_mode: str) -> str:
    approval_note = ""
    if approval_mode == "on-write":
        approval_note = (
            "- Prefer read-only inspection first.\n"
            "- If you decide a write is necessary, briefly state the intended write before doing it.\n"
        )
    elif approval_mode == "never":
        approval_note = "- Proceed without waiting for extra approval prompts.\n"
    return textwrap.dedent(
        f"""
        You are running inside Codex Agent Loop fallback mode.

        Workspace root: {workspace_root}
        Requested max turns: {max_turns}
        Requested approval mode: {approval_mode}

        Important:
        - Treat the requested max turns as a strict budget for major inspect/edit/test phases.
        - Prefer to finish within that budget.
        - If the task can be completed read-only, avoid writes entirely.
        - Verify any important result before concluding.
        {approval_note}

        Task:
        {task}
        """
    ).strip()


def parse_codex_exec_jsonl(output: str) -> str:
    last_text = ""
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message" and isinstance(item.get("text"), str):
                last_text = item["text"]
    return last_text


def run_codex_exec_loop(
    *,
    task: str,
    workspace_root: Path,
    run_dir: Path,
    model: str,
    reasoning_effort: str,
    approval_mode: str,
    max_turns: int,
) -> dict[str, Any]:
    if approval_mode == "always":
        raise LoopError("approval_mode=always is not supported in codex-exec fallback mode.")
    if shutil.which("codex") is None:
        raise LoopError("codex executable not found on PATH for fallback execution.")

    prompt = build_codex_exec_prompt(task, workspace_root, max_turns, approval_mode)
    cmd = [
        "codex",
        "exec",
        "--json",
        "-C",
        str(workspace_root),
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning_effort}"',
    ]
    if not has_git_repo(workspace_root):
        cmd.append("--skip-git-repo-check")
    cmd.extend(["-s", "workspace-write"])
    cmd.append(prompt)

    proc = subprocess.run(
        cmd,
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    (run_dir / "codex_exec.stdout.jsonl").write_text(proc.stdout, encoding="utf-8")
    (run_dir / "codex_exec.stderr.txt").write_text(proc.stderr, encoding="utf-8")

    final_text = parse_codex_exec_jsonl(proc.stdout)
    if proc.returncode != 0 and not final_text:
        raise LoopError(
            "codex exec fallback failed"
            + (f": {proc.stderr.strip()}" if proc.stderr.strip() else "")
        )

    summary = {
        "status": "completed" if proc.returncode == 0 else "completed_with_warnings",
        "stop_reason": "codex_exec_fallback",
        "backend": "codex-exec",
        "run_dir": str(run_dir),
        "state_path": str(run_dir / "state.json"),
        "turns_used": 1,
        "max_turns": max_turns,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "approval_mode": approval_mode,
        "workspace_root": str(workspace_root),
        "task": task,
        "files_changed": [],
        "verification_commands": [],
        "final_answer": final_text or proc.stderr.strip(),
    }
    write_state(run_dir / "state.json", {**summary, "updated_at": now_ts()})
    return summary


def print_demo_intro(workspace_root: Path) -> None:
    print("Codex Agent Loop onboarding demo")
    print(f"Workspace: {workspace_root}")
    print("This first run is safe and read-only.")
    print()


def print_demo_next_steps() -> None:
    demo_write_dir = Path(tempfile.mkdtemp(prefix="codex-agent-loop-demo-"))
    script = quoted_script_command()
    print("\nQuickstart complete.")
    print("Next commands to try:")
    print(f"1) Setup check:\n   {script} --doctor")
    print(
        "2) Tiny write demo in a throwaway directory:\n"
        f"   {script} --cwd {shlex.quote(str(demo_write_dir))} --approval-mode never "
        '"Create a file named hello.txt containing exactly hello from codex-agent-loop."'
    )
    print(
        "3) Real repo task:\n"
        f'   {script} --max-turns 8 --approval-mode on-write "Fix the failing tests and verify the result"'
    )


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    runs_dir = Path(args.runs_dir).expanduser().resolve()
    workspace_root = Path(args.cwd).expanduser().resolve()

    try:
        if args.doctor:
            report = build_doctor_report(args.cwd)
            if args.json:
                print(json.dumps(report, ensure_ascii=False))
            else:
                print_doctor_report(report)
            return 0 if report["backend"] != "unavailable" else 1

        task = task_from_args(args)
        if args.demo and args.max_turns == DEFAULT_MAX_TURNS:
            args.max_turns = 3

        if args.resume:
            state_path = Path(args.resume).expanduser().resolve()
            resume_state = json.loads(state_path.read_text())
            run_dir = Path(resume_state["run_dir"]).expanduser().resolve()
            workspace_root = normalize_workspace(resume_state.get("workspace_root", args.cwd))
        else:
            resume_state = None
            workspace_root = normalize_workspace(args.cwd)
            run_dir = create_run_dir(runs_dir)

        backend_report = build_backend_report()
        if not args.json:
            if args.demo:
                print_demo_intro(workspace_root)
            print_backend_banner(backend_report)

        client: OpenAI | None
        if backend_report["backend"] == "responses":
            try:
                client = ensure_openai_client()
            except Exception as exc:
                if backend_report["codex_available"] and not (args.resume or args.approve_pending):
                    client = None
                    backend_report = {
                        **backend_report,
                        "backend": "codex-exec",
                        "backend_label": backend_label("codex-exec"),
                        "backend_note": (
                            "Responses backend initialization failed; falling back to codex exec. "
                            f"Reason: {exc}"
                        ),
                    }
                else:
                    raise
        elif backend_report["backend"] == "codex-exec":
            client = None
        else:
            raise LoopError("No usable backend found. Run with --doctor for setup guidance.")

        if client is None:
            if args.resume or args.approve_pending:
                raise LoopError(
                    "Resume/approval state requires an OPENAI_API_KEY-backed Responses backend. "
                    "Current environment only has Codex/ChatGPT auth."
                )
            summary = run_codex_exec_loop(
                task=task,
                workspace_root=workspace_root,
                run_dir=run_dir,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                approval_mode=args.approval_mode,
                max_turns=args.max_turns,
            )
        else:
            summary = run_loop(
                client,
                task=task,
                workspace_root=workspace_root,
                run_dir=run_dir,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                approval_mode=args.approval_mode,
                max_turns=args.max_turns,
                resume_state=resume_state,
                approve_pending=args.approve_pending,
            )
    except ApprovalPause as pause:
        return int(pause.code)
    except Exception as exc:
        error_summary = {
            "status": "failed",
            "stop_reason": "error",
            "error": str(exc),
            "workspace_root": str(workspace_root),
        }
        if args.json:
            print(json.dumps(error_summary, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print_human_summary(summary)
        if args.demo:
            print_demo_next_steps()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
