# Codex Agent Loop

[![Version](https://img.shields.io/badge/version-0.2.2-111827)](./.codex-plugin/plugin.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3b82f6.svg)](./scripts/agent_loop.py)

Bounded, resumable Claude-Code-style coding loops for Codex.

GitHub: https://github.com/SiluPanda/codex-agent-loop

## At a glance

- run inside Codex with the bundled Agent Loop entrypoint
- start safely with the built-in doctor and demo flow
- use simple time-based or turn-based budgets
- keep logs and state under `~/.codex/agent-loop/runs/`

## Quickstart

### 1) Install it

Clone the repo and run the installer script in `scripts/install.py`.

The installer:

- copies the plugin into `~/.codex/plugins/agent-loop`
- merges the marketplace entry into `~/.agents/plugins/marketplace.json`
- backs up the previous plugin install and marketplace file if they exist

### 2) Enable it in Codex

1. restart Codex
2. open `/plugins`
3. install or enable **Agent Loop**
4. start a new thread

### 3) Terminal example

Run a real task from inside Codex:

```text
$agent-loop 10m example task
```

Animated Codex CLI UX:

![Codex Agent Loop demo GIF](docs/assets/agent-loop-demo.gif)

## What success looks like

You should see:

- a status summary
- a run directory like `~/.codex/agent-loop/runs/<timestamp>-<id>/`

## Friendly approval modes

- `safe` = `on-write` (default)
- `hands-off` = `never`
- `review-everything` = `always`

## What it includes

- `agent-loop` skill
- `commands/run.md` command definition for Codex builds that surface plugin commands
- `scripts/install.py` installer
- environment check support
- onboarding demo support
- shorthand budgets
- local run logs and resumable approval state

## Docs

- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Manual install](docs/manual-install.md)

## Repo layout

```text
.codex-plugin/plugin.json
commands/run.md
docs/
scripts/agent_loop.py
scripts/install.py
skills/agent-loop/SKILL.md
tests/
```
