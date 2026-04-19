# Manual install

If you do not want to use `scripts/install.py`, install manually.

## 1) Copy the plugin

Place this repo at:

```bash
~/.codex/plugins/codex-agent-loop
```

## 2) Merge the marketplace entry

Add this plugin entry to your existing `~/.agents/plugins/marketplace.json`.

Do not overwrite your whole marketplace file if you already have other plugins.

```json
{
  "name": "codex-agent-loop",
  "source": {
    "source": "local",
    "path": "./.codex/plugins/codex-agent-loop"
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
- install or enable `Codex Agent Loop`

## 4) Verify

Run:

```bash
python3 ~/.codex/plugins/codex-agent-loop/scripts/agent_loop.py --doctor
```
