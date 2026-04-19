# Codex Agent Loop

A local Codex plugin that gives Codex a Claude-Code-style loop runner for bounded coding tasks.

GitHub: https://github.com/SiluPanda/codex-agent-loop

## 60-second quickstart

### 1) Install it

Clone anywhere, then run the installer:

```bash
git clone https://github.com/SiluPanda/codex-agent-loop.git
cd codex-agent-loop
python3 scripts/install.py
```

The installer:

- copies the plugin into `~/.codex/plugins/codex-agent-loop`
- merges the marketplace entry into `~/.agents/plugins/marketplace.json`
- backs up the previous plugin install and marketplace file if they exist

### 2) Enable it in Codex

After install:

1. restart Codex
2. open `/plugins`
3. install or enable **Codex Agent Loop**
4. start a new thread

### 3) Use it inside Codex CLI

Primary UX:

```text
/agent-loop --doctor
/agent-loop --demo
/agent-loop 10m fix the failing tests and verify the result
```

Shorthand budgets:

- `10m` = 10 minutes
- `1h` = 1 hour
- `5t` = 5 turns

### 4) First commands to try

Check your setup:

```text
/agent-loop --doctor
```

Run the guided demo:

```text
/agent-loop --demo
```

This first demo is safe and read-only.

Run a real task:

```text
/agent-loop 10m --approval-mode on-write fix the failing tests and verify the result
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

## Preview

Animated write-flow demo:

![Codex Agent Loop demo GIF](docs/assets/agent-loop-demo.gif)

CLI help:

![Codex Agent Loop help screenshot](docs/assets/agent-loop-help.png)

Doctor output:

![Codex Agent Loop doctor screenshot](docs/assets/agent-loop-doctor.png)

Read-only inspection example:

![Codex Agent Loop read-only screenshot](docs/assets/agent-loop-readonly.png)

Write example:

![Codex Agent Loop write screenshot](docs/assets/agent-loop-write.png)

## What it includes

- `/agent-loop` command
- `codex-agent-loop` skill
- `scripts/install.py` installer
- `--doctor` environment check
- `--demo` onboarding run
- shorthand budgets like `10m` and `5t`
- local run logs and resumable approval state

## Primary UX

This plugin is meant to be used from inside Codex as a slash command:

```text
/agent-loop ...
```

## Common commands

### Setup diagnosis

```text
/agent-loop --doctor
```

### Guided demo

```text
/agent-loop --demo
```

### Claude-Code-style shorthand

```text
/agent-loop 10m fix the failing tests and verify the result
```

### Turn-capped run

```text
/agent-loop 5t refactor this module
```

### Read-only inspection

```text
/agent-loop 5t inspect this workspace and report what files exist. do not modify anything
```

### Tiny write demo

```text
/agent-loop 5t --approval-mode never create a file named hello.txt containing exactly hello from codex-agent-loop
```

## Docs

- [Troubleshooting](docs/troubleshooting.md)
- [Architecture](docs/architecture.md)
- [Development](docs/development.md)
- [Manual install](docs/manual-install.md)

## Repo layout

```text
.codex-plugin/plugin.json
commands/agent-loop.md
docs/
scripts/agent_loop.py
scripts/install.py
skills/codex-agent-loop/SKILL.md
tests/
```
