# Codex Agent Loop

[![Version](https://img.shields.io/badge/version-0.2.2-111827)](./.codex-plugin/plugin.json)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3b82f6.svg)](./scripts/agent_loop.py)

Bounded, resumable Claude-Code-style coding loops for Codex.

GitHub: https://github.com/SiluPanda/codex-agent-loop

## At a glance

- run inside Codex with `$agent-loop`
- start safely with `--doctor` and `--demo`
- use simple budgets like `10m`, `1h`, and `5t`
- keep logs and state under `~/.codex/agent-loop/runs/`

### Most common commands

```text
$agent-loop --doctor
$agent-loop --demo
$agent-loop 10m --approval-mode on-write fix the failing tests and verify the result
```

## 60-second quickstart

### 1) Install it

Clone anywhere, then run the installer:

```bash
git clone https://github.com/SiluPanda/codex-agent-loop.git
cd codex-agent-loop
python3 scripts/install.py
```

The installer:

- copies the plugin into `~/.codex/plugins/agent-loop`
- merges the marketplace entry into `~/.agents/plugins/marketplace.json`
- backs up the previous plugin install and marketplace file if they exist

### 2) Enable it in Codex

After install:

1. restart Codex
2. open `/plugins`
3. install or enable **Agent Loop**
4. start a new thread

### 3) Use it inside Codex

Supported Codex entrypoint:

```text
$agent-loop
```

Common first prompts:

```text
$agent-loop --doctor
$agent-loop --demo
$agent-loop 10m fix the failing tests and verify the result
```

Direct runner outside Codex:

```text
python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py --doctor
```

Current public Codex builds do not reliably surface plugin-defined slash
commands. This repo still includes `commands/run.md` for builds that do, but if
`/agent-loop:run` is unrecognized, use `$agent-loop` instead.

Shorthand budgets:

- `10m` = 10 minutes
- `1h` = 1 hour
- `5t` = 5 turns

### 4) First commands to try

Check your setup:

```text
$agent-loop --doctor
```

Run the guided demo:

```text
$agent-loop --demo
```

This first demo is safe and read-only.

Run a real task:

```text
$agent-loop 10m --approval-mode on-write fix the failing tests and verify the result
```

## What success looks like

You should see:

- a status summary
- a run directory like `~/.codex/agent-loop/runs/<timestamp>-<id>/`

## Friendly approval modes

- `safe` = `on-write` (default)
- `hands-off` = `never`
- `review-everything` = `always`

The CLI flags stay:

- `--approval-mode on-write`
- `--approval-mode never`
- `--approval-mode always`

## Final demo

### Codex chat demo

Animated end-to-end demo:

![Codex Agent Loop demo GIF](docs/assets/agent-loop-demo.gif)

### Setup and verification screens

CLI help:

![Codex Agent Loop help screenshot](docs/assets/agent-loop-help.png)

Doctor output:

![Codex Agent Loop doctor screenshot](docs/assets/agent-loop-doctor.png)

Read-only inspection example:

![Codex Agent Loop read-only screenshot](docs/assets/agent-loop-readonly.png)

Write example:

![Codex Agent Loop write screenshot](docs/assets/agent-loop-write.png)

## What it includes

- `agent-loop` skill
- `commands/run.md` command definition for Codex builds that surface plugin commands
- `scripts/install.py` installer
- `--doctor` environment check
- `--demo` onboarding run
- shorthand budgets like `10m` and `5t`
- local run logs and resumable approval state

## User guide

### Choose your entrypoint

- **Inside Codex:** use `$agent-loop ...`
- **Outside Codex:** use `python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py ...`
- **Optional slash command:** if your Codex build exposes plugin-defined slash commands, `/agent-loop:run ...` is equivalent

### Recommended first-run flow

1. Install the plugin with `python3 scripts/install.py`
2. Restart Codex
3. Enable **Agent Loop** from `/plugins`
4. Start a new thread
5. Run `$agent-loop --doctor`
6. Run `$agent-loop --demo`
7. Run a real task with a budget like `10m` or `5t`

### Budgets

- `10m` = run for up to 10 minutes
- `1h` = run for up to 1 hour
- `5t` = run for up to 5 turns

### Approval modes

- `--approval-mode on-write` = safe default
- `--approval-mode never` = hands-off
- `--approval-mode always` = review every action

### Run artifacts

Each run writes logs and state under:

```text
~/.codex/agent-loop/runs/<timestamp>-<id>/
```

Typical files:

- `state.json`
- `responses.jsonl`
- `events.jsonl`
- `codex_exec.stdout.jsonl`
- `codex_exec.stderr.txt`

## Primary UX

This plugin is meant to be used from inside Codex primarily as a bundled skill:

```text
$agent-loop ...
```

If your Codex build exposes plugin-defined slash commands, the equivalent
command is:

```text
/agent-loop:run ...
```

## Common commands

### Setup diagnosis

```text
$agent-loop --doctor
```

### Guided demo

```text
$agent-loop --demo
```

### Claude-Code-style shorthand

```text
$agent-loop 10m fix the failing tests and verify the result
```

### Turn-capped run

```text
$agent-loop 5t refactor this module
```

### Read-only inspection

```text
$agent-loop 5t inspect this workspace and report what files exist. do not modify anything
```

### Tiny write demo

```text
$agent-loop 5t --approval-mode never create a file named hello.txt containing exactly hello from agent-loop
```

## Terminal demo

If you want to verify the runner outside Codex first, this is the fastest path.

### 1) Install locally

```bash
python3 scripts/install.py
```

### 2) Run doctor

```text
$ python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py --doctor
Codex Agent Loop doctor
Installed plugin copy: yes (~/.codex/plugins/agent-loop)
Marketplace entry: yes (~/.agents/plugins/marketplace.json)
Recommended Codex entrypoint: $agent-loop
Plugin slash command: /agent-loop:run
Selected backend: codex exec fallback
Next step: python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py --demo
```

### 3) Run the safe onboarding demo

```text
$ python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py --demo
Codex Agent Loop onboarding demo
This first run is safe and read-only.

Status: completed
Stop reason: codex_exec_fallback
Turns used: 1/3
Run dir: ~/.codex/agent-loop/runs/<timestamp>-<id>

Final answer:
- inspected the workspace read-only
- made no file changes
```

### 4) Run a real task

```bash
python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py \
  10m \
  --approval-mode on-write \
  "Fix the failing tests and verify the result"
```

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
