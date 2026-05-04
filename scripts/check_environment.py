#!/usr/bin/env python3
import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_MODULES = {
    "opendataloader_pdf": "opendataloader-pdf",
    "fitz": "PyMuPDF",
}


def module_ok(module_name: str):
    return importlib.util.find_spec(module_name) is not None


def java_status():
    java = shutil.which("java")
    if not java:
        return {"ok": False, "path": None, "version": None}

    result = subprocess.run(
        [java, "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    version = (result.stderr or result.stdout).splitlines()[0] if (result.stderr or result.stdout) else ""
    return {"ok": result.returncode == 0, "path": java, "version": version}


def workspace_status(vault: Path):
    thesis = vault / "thesis"
    folders = {
        "pdf": thesis / "pdf",
        "fin": thesis / "fin",
        "trn": thesis / "trn",
    }
    return {name: {"path": str(path), "exists": path.exists()} for name, path in folders.items()}


def main():
    parser = argparse.ArgumentParser(description="Check paper-translate runtime dependencies.")
    parser.add_argument("--vault", default=str(Path.cwd()), help="Obsidian vault root")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    modules = {
        module: {"ok": module_ok(module), "package": package}
        for module, package in REQUIRED_MODULES.items()
    }
    payload = {
        "python": sys.executable,
        "modules": modules,
        "java": java_status(),
        "workspace": workspace_status(vault),
    }
    payload["ok"] = all(item["ok"] for item in modules.values()) and payload["java"]["ok"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not payload["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
