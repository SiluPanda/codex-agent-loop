# Architecture

## Overview

Codex Agent Loop provides a bounded local skill-first workflow for coding tasks in Codex CLI.

It exposes:

- a primary Codex skill alias: `$agent-loop`
- an optional plugin command definition at `commands/run.md` for Codex builds that surface plugin commands
- an installer: `scripts/install.py`

## User-facing workflow

The primary user experience is:

1. run `python3 scripts/install.py`
2. restart Codex
3. enable the plugin from `/plugins`
4. start a new thread
5. use `$agent-loop ...`
6. optionally use `/agent-loop:run ...` if your Codex build surfaces plugin-defined slash commands

## Run artifacts

Run logs are stored under:

```text
~/.codex/agent-loop/runs/<timestamp>-<id>/
```

Typical files:

- `state.json`
- `responses.jsonl`
- `events.jsonl`
- `codex_exec.stdout.jsonl`
- `codex_exec.stderr.txt`
