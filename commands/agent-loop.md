---
description: Run a bounded, Claude-Code-style coding loop with OpenAI-native shell/apply_patch tooling.
argument-hint: [task] [--max-turns N] [--approval-mode on-write|always|never] [--model MODEL] [--reasoning-effort low|medium|high|xhigh] [--resume STATE] [--approve-pending]
allowed-tools: [Read, Bash]
---

# /agent-loop

Run the local Codex Agent Loop runner at:

`~/.codex/plugins/codex-agent-loop/scripts/agent_loop.py`

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
4. Run:

```bash
python3 ~/.codex/plugins/codex-agent-loop/scripts/agent_loop.py $ARGUMENTS
```

The runner prefers direct Responses API execution when an API key is available and otherwise falls back to `codex exec`.

5. If the runner pauses for approval:
   - summarize the pending command or patch
   - show the saved state path
   - ask whether to resume with `--approve-pending`
6. If the runner completes, report:
   - stop reason
   - turns used
   - files changed
   - verification commands
   - final answer
7. Do not claim any command or patch executed unless the runner output shows it.

## Default flags

- `--max-turns 8`
- `--approval-mode on-write`
- `--model gpt-5.4`
- `--reasoning-effort high`
