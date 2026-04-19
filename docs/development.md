# Development

## Local checks

Syntax:

```bash
python3 -m py_compile scripts/agent_loop.py scripts/install.py tests/test_agent_loop.py tests/test_install.py
```

Tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

## Key files

- `scripts/agent_loop.py` — main runner
- `scripts/install.py` — installer and marketplace merge
- `commands/run.md` — optional plugin command definition for Codex builds that surface plugin commands
- `skills/agent-loop/SKILL.md` — skill guidance

## Release flow

Typical flow:

1. update code/docs
2. run tests
3. commit and push
4. tag a version
5. create a GitHub release
