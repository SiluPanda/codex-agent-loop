# Architecture

## Overview

Codex Agent Loop provides a bounded local slash-command workflow for coding tasks in Codex CLI.

It exposes:

- a Codex command: `/agent-loop`
- a Codex skill: `codex-agent-loop`
- an installer: `scripts/install.py`

## User-facing workflow

The primary user experience is:

1. run `python3 scripts/install.py`
2. restart Codex
3. enable the plugin from `/plugins`
4. start a new thread
5. use `/agent-loop ...`

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
