# Troubleshooting

## Plugin does not appear in `/plugins`

Run:

```bash
python3 ~/.codex/plugins/codex-agent-loop/scripts/agent_loop.py --doctor
```

Check:

- `Installed plugin copy: yes`
- `Marketplace entry: yes`

If either is missing, re-run:

```bash
python3 scripts/install.py
```

## Why did it use fallback mode?

Fallback mode means:

- no `OPENAI_API_KEY` was found
- Codex was available locally

Run:

```bash
python3 scripts/agent_loop.py --doctor
```

Look at:

- `API key source`
- `Selected backend`

## Why can’t I resume a paused run?

Resume support requires the OpenAI Responses backend.

It is unavailable in `codex exec` fallback mode.

## Why did `approval_mode=always` fail?

`approval_mode=always` only works on the OpenAI Responses backend.

In fallback mode, use:

- `--approval-mode on-write`
- or `--approval-mode never`

## “No OPENAI_API_KEY found”

The runner checks:

1. `OPENAI_API_KEY` in the environment
2. `~/.codex/auth.json`
3. fallback to `codex exec`

If you want resumable approval-state support, provide an API key.

## “codex executable not found on PATH”

Install Codex or make sure `codex` is on your `PATH`.

Then re-run:

```bash
python3 scripts/agent_loop.py --doctor
```
