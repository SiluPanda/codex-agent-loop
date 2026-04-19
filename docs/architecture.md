# Architecture

## Overview

Codex Agent Loop provides a bounded local runner for coding tasks.

It exposes:

- a Codex command: `/agent-loop`
- a Codex skill: `codex-agent-loop`
- a Python runner: `scripts/agent_loop.py`
- an installer: `scripts/install.py`

## Execution backends

### OpenAI Responses backend

Used when:

- the OpenAI Python package is available
- an API key is available

This backend uses:

- `shell`
- `apply_patch`

and can pause/resume approval state.

### `codex exec` fallback

Used when:

- no API key is available
- local Codex is installed

This keeps the plugin useful on ChatGPT-authenticated Codex installs, but it cannot support host-managed resume/approval state.

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
