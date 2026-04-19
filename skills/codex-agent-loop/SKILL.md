---
name: codex-agent-loop
description: Run bounded, resumable OpenAI-native coding loops with shell and apply_patch, similar to Claude Code agent loops. Use when the user asks for a loop, autonomous iteration, or a persistent inspect-edit-test cycle with a turn cap.
---

# Codex Agent Loop

Use this skill for multi-step coding tasks that need a bounded agent loop instead of a single local step.

## When to use

- The user says loop, agent loop, autonomous, keep iterating, or mentions Claude Code.
- The work will likely require repeated inspect/edit/test cycles.
- A turn cap or explicit approval boundary is useful.

## Defaults

- `--max-turns 8`
- `--approval-mode on-write`
- `--model gpt-5.4`
- `--reasoning-effort high`

## Invocation

Prefer the explicit slash command:

```text
/agent-loop <task>
```

Or run the script directly:

```bash
python3 ~/.codex/plugins/codex-agent-loop/scripts/agent_loop.py --max-turns 8 --approval-mode on-write --model gpt-5.4 --reasoning-effort high "<task>"
```

If `OPENAI_API_KEY` is unavailable, the runner automatically falls back to `codex exec`.

## Onboarding helpers

- `--doctor` explains which backend will run and whether setup is complete.
- `--demo` runs a safe read-only first-run example and suggests next commands.

Approval modes in plain English:

- `on-write` = safe
- `never` = hands-off
- `always` = review-everything

## Approval behavior

- `on-write` auto-runs read-only shell inspection commands.
- `on-write` pauses before write-like shell commands and all patches.
- Use `--resume <state-file> --approve-pending` only after the user explicitly approves the paused action.

## Run artifacts

The runner stores logs and resumable state under:

`~/.codex/agent-loop/runs/`
