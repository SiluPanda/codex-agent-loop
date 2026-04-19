#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

PLUGIN_NAME = "codex-agent-loop"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = Path.home() / ".codex" / "plugins" / PLUGIN_NAME
DEFAULT_MARKETPLACE = Path.home() / ".agents" / "plugins" / "marketplace.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Codex Agent Loop into ~/.codex/plugins and merge the marketplace entry."
    )
    parser.add_argument("--source", default=str(REPO_ROOT), help="Source repo/plugin directory.")
    parser.add_argument("--target", default=str(DEFAULT_TARGET), help="Installed plugin directory.")
    parser.add_argument(
        "--marketplace",
        default=str(DEFAULT_MARKETPLACE),
        help="Path to marketplace.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions that would be taken without writing changes.",
    )
    return parser.parse_args()


def now_slug() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def plugin_entry(target_path: Path) -> dict[str, Any]:
    return {
        "name": PLUGIN_NAME,
        "source": {
            "source": "local",
            "path": str(target_path).replace(str(Path.home()), "."),
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Coding",
    }


def default_marketplace_document() -> dict[str, Any]:
    return {
        "name": "local-plugins",
        "interface": {"displayName": "Local Plugins"},
        "plugins": [],
    }


def load_marketplace(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_marketplace_document()
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError(f"Unsupported marketplace format in {path}: expected a JSON object.")
    plugins = data.get("plugins")
    if plugins is None:
        data["plugins"] = []
    elif not isinstance(plugins, list):
        raise RuntimeError(f"Unsupported marketplace format in {path}: 'plugins' must be a list.")
    data.setdefault("name", "local-plugins")
    data.setdefault("interface", {"displayName": "Local Plugins"})
    return data


def merge_plugin_entry(document: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    plugins = document.setdefault("plugins", [])
    assert isinstance(plugins, list)
    for index, plugin in enumerate(plugins):
        if isinstance(plugin, dict) and plugin.get("name") == entry["name"]:
            plugins[index] = entry
            break
    else:
        plugins.append(entry)
    return document


def backup_existing_path(path: Path, dry_run: bool) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.backup-{now_slug()}")
    if not dry_run:
        shutil.copy2(path, backup) if path.is_file() else shutil.copytree(path, backup)
    return backup


def copy_plugin_tree(source: Path, target: Path, dry_run: bool) -> Path | None:
    source = source.resolve()
    target = target.expanduser().resolve()
    if source == target:
        return None

    backup = None
    if target.exists():
        backup = target.with_name(f"{target.name}.backup-{now_slug()}")
        if not dry_run:
            shutil.move(str(target), str(backup))

    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store"),
        )
    return backup


def write_marketplace(path: Path, document: dict[str, Any], dry_run: bool) -> Path | None:
    backup = backup_existing_path(path, dry_run)
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return backup


def print_summary(
    *,
    source: Path,
    target: Path,
    marketplace: Path,
    plugin_backup: Path | None,
    marketplace_backup: Path | None,
    dry_run: bool,
) -> None:
    mode = "Dry run" if dry_run else "Install complete"
    print(mode)
    print(f"Source: {source}")
    print(f"Target: {target}")
    print(f"Marketplace: {marketplace}")
    if plugin_backup:
        print(f"Plugin backup: {plugin_backup}")
    if marketplace_backup:
        print(f"Marketplace backup: {marketplace_backup}")
    print("Next steps:")
    print("1) Restart Codex")
    print("2) Open /plugins")
    print("3) Install or enable Codex Agent Loop")
    print(f"4) Run: python3 {target / 'scripts' / 'agent_loop.py'} --doctor")
    print(f"5) Run: python3 {target / 'scripts' / 'agent_loop.py'} --demo")


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    target = Path(args.target).expanduser().resolve()
    marketplace = Path(args.marketplace).expanduser().resolve()

    if not source.exists():
        print(f"Error: source directory does not exist: {source}", file=sys.stderr)
        return 1
    if not (source / ".codex-plugin" / "plugin.json").exists():
        print(f"Error: source does not look like a Codex plugin: {source}", file=sys.stderr)
        return 1

    entry = plugin_entry(target)
    document = merge_plugin_entry(load_marketplace(marketplace), entry)

    plugin_backup = copy_plugin_tree(source, target, args.dry_run)
    marketplace_backup = write_marketplace(marketplace, document, args.dry_run)

    print_summary(
        source=source,
        target=target,
        marketplace=marketplace,
        plugin_backup=plugin_backup,
        marketplace_backup=marketplace_backup,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
