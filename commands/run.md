---
description: Run a bounded, Claude-Code-style coding loop with onboarding helpers like --doctor, --demo, and shorthand budgets like 10m.
argument-hint: [10m|1h|5t] [task] [--max-turns N] [--max-seconds N] [--approval-mode on-write|always|never] [--model MODEL] [--reasoning-effort low|medium|high|xhigh] [--resume STATE] [--approve-pending] [--doctor] [--demo]
allowed-tools: [Read, Bash]
---

# /agent-loop:run

This command definition is included for Codex builds that surface plugin-defined
slash commands. If `/agent-loop:run` is unrecognized in your Codex build, use
`$agent-loop` instead.

This plugin command is namespaced by plugin id, so invoke it as:

`/agent-loop:run ...`

Run the local Codex Agent Loop runner at:

`~/.codex/plugins/agent-loop/scripts/agent_loop.py`

## When to use

- The user explicitly asks for a loop, autonomous run, or Claude-Code-style persistence.
- The task likely needs multiple inspect/edit/test cycles.
- You want a bounded run with a turn cap and resumable approval pauses.

## Arguments

The user invoked this command with: `$ARGUMENTS`

## Workflow

1. Treat `$ARGUMENTS` as CLI flags plus the task text.
2. If `--resume` is present, run the script with that resume path.
3. Only add `--approve-pending` after the user explicitly approves the paused action.
4. If `--doctor` is present, run the environment check and summarize the result.
5. If `--demo` is present, run the safe onboarding demo.
6. Approval modes in human terms:
   - `on-write` = safe
   - `never` = hands-off
   - `always` = review-everything
7. If the first positional token looks like `10m`, `1h`, or `5t`, treat it as a shorthand budget:
   - `m` = minutes
   - `h` = hours
   - `t` = turns
8. Run:

```bash
python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py $ARGUMENTS
```

9. If the runner pauses for approval:
   - summarize the pending command or patch
   - show the saved state path
   - ask whether to resume with `--approve-pending`
10. If the runner completes, report:
   - stop reason
   - turns used
   - files changed
   - verification commands
   - final answer
11. Do not claim any command or patch executed unless the runner output shows it.

## Default flags

- `--max-turns 8`
- `--approval-mode on-write`
- `--model gpt-5.4`
- `--reasoning-effort high`

## Examples

- `/agent-loop:run 10m fix the failing tests`
- `/agent-loop:run 5t refactor the auth module`
- `$agent-loop 10m fix the failing tests`
