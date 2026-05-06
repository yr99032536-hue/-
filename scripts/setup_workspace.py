#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path


WORKSPACE_NAME = "논문"
LEGACY_WORKSPACE_NAME = "thesis"
SUBDIRS = ("pdf", "fin", "trn")


def migrate_legacy_workspace(vault: Path):
    legacy = vault / LEGACY_WORKSPACE_NAME
    target = vault / WORKSPACE_NAME
    migrated = []

    if legacy.exists() and not target.exists():
        legacy.rename(target)
        return {"migrated": True, "from": str(legacy), "to": str(target), "items": ["entire_workspace"]}

    if legacy.exists() and target.exists():
        for name in SUBDIRS:
            source = legacy / name
            destination = target / name
            if source.exists() and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                migrated.append(name)
        remaining = list(legacy.iterdir()) if legacy.exists() else []
        if legacy.exists() and not remaining:
            legacy.rmdir()
        return {"migrated": bool(migrated), "from": str(legacy), "to": str(target), "items": migrated}

    return {"migrated": False, "from": str(legacy), "to": str(target), "items": []}


def ensure_workspace(vault: Path):
    workspace = vault / WORKSPACE_NAME
    created = []
    for name in SUBDIRS:
        path = workspace / name
        if not path.exists():
            created.append(str(path))
        path.mkdir(parents=True, exist_ok=True)
    return workspace, created


def main():
    parser = argparse.ArgumentParser(description="Create the paper translation workspace folders in an Obsidian vault.")
    parser.add_argument("--vault", required=True, help="Path to the Obsidian vault root")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    migration = migrate_legacy_workspace(vault)
    workspace, created = ensure_workspace(vault)

    payload = {
        "workspace": str(workspace),
        "created": created,
        "migration": migration,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
