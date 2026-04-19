# Troubleshooting

## Plugin does not appear in `/plugins`

Check:

- `python3 scripts/install.py` completed successfully
- Codex was restarted after installation
- `~/.agents/plugins/marketplace.json` still contains the plugin entry

If either is missing, re-run:

```bash
python3 scripts/install.py
```

Then restart Codex and start a new thread.

## Slash command is not available

Make sure you:

- installed the plugin from `/plugins`
- started a new thread after installation
- restarted Codex after updating the local plugin

## `approval_mode=always` does not behave how I want

Use one of these instead:

- `--approval-mode on-write`
- `--approval-mode never`

## “codex executable not found on PATH”

Install Codex or make sure `codex` is on your `PATH`.

Then reinstall the plugin if needed:

```bash
python3 scripts/install.py
```
