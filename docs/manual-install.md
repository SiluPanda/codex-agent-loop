# Manual install

If you do not want to use `scripts/install.py`, install manually.

## 1) Copy the plugin

Place this repo at:

```bash
~/.codex/plugins/agent-loop
```

## 2) Merge the marketplace entry

Add this plugin entry to your existing `~/.agents/plugins/marketplace.json`.

Do not overwrite your whole marketplace file if you already have other plugins.

```json
{
  "name": "agent-loop",
  "source": {
    "source": "local",
    "path": "./.codex/plugins/agent-loop"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Coding"
}
```

## 3) Restart Codex

Then:

- open `/plugins`
- install or enable `Agent Loop`

## 4) Verify

Start a new thread in Codex and run:

```text
$agent-loop --doctor
```

Current public Codex builds may not surface plugin-defined slash commands. If
`/agent-loop:run` is unrecognized, use `$agent-loop` instead.

If you only want to test the local runner first, you can also run:

```bash
python3 ~/.codex/plugins/agent-loop/scripts/agent_loop.py --doctor
```
