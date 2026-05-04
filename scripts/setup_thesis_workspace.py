#!/usr/bin/env python3
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Create thesis workspace folders in an Obsidian vault.")
    parser.add_argument("--vault", required=True, help="Path to the Obsidian vault root")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    thesis = vault / "thesis"
    for name in ("pdf", "fin", "trn"):
        path = thesis / name
        path.mkdir(parents=True, exist_ok=True)
        print(path)


if __name__ == "__main__":
    main()
