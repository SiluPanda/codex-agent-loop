# Development

## Local checks

Syntax:

```bash
# Writes .pyc files, so it needs a writable filesystem.
python3 -m py_compile scripts/agent_loop.py scripts/install.py tests/test_agent_loop.py tests/test_install.py
```

Read-only-friendly syntax check:

```bash
python3 - <<'PY'
from pathlib import Path

for path in [
    Path("scripts/agent_loop.py"),
    Path("scripts/install.py"),
    Path("tests/test_agent_loop.py"),
    Path("tests/test_install.py"),
]:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print("Syntax OK")
PY
```

Tests:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Note:

- tests that need temporary directories will skip automatically if the environment does not provide a writable temp directory
- if you are running in a sandbox, set `TMPDIR` to a writable location when needed

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
