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
WORKSPACE_NAME = "논문"
LEGACY_WORKSPACE_NAME = "thesis"


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
    workspace = vault / WORKSPACE_NAME
    legacy = vault / LEGACY_WORKSPACE_NAME
    folders = {
        "pdf": workspace / "pdf",
        "fin": workspace / "fin",
        "trn": workspace / "trn",
    }
    return {
        "name": WORKSPACE_NAME,
        "path": str(workspace),
        "legacy_path": str(legacy),
        "legacy_exists": legacy.exists(),
        "folders": {name: {"path": str(path), "exists": path.exists()} for name, path in folders.items()},
    }


def build_messages(modules, java, workspace):
    messages = []

    missing_packages = [item["package"] for item in modules.values() if not item["ok"]]
    if missing_packages:
        joined = ", ".join(missing_packages)
        messages.append(f"Missing Python packages: {joined}. Run `bash scripts/install.sh --vault <vault>`.")

    if not java["ok"]:
        messages.append("Java is missing or not runnable. Install Java 11+ or rerun `bash scripts/install.sh --vault <vault> --install-java` on apt-based Linux.")

    missing_folders = [name for name, item in workspace["folders"].items() if not item["exists"]]
    if missing_folders:
        joined = ", ".join(f"{WORKSPACE_NAME}/{name}" for name in missing_folders)
        messages.append(f"Workspace folders are missing: {joined}. Run `bash scripts/install.sh --vault <vault>`.")

    if workspace["legacy_exists"]:
        messages.append(f"Legacy workspace `{LEGACY_WORKSPACE_NAME}/` is still present. The installer will migrate it to `{WORKSPACE_NAME}/`.")

    if not messages:
        messages.append("Environment looks good. You can place PDFs in `논문/pdf` and run `/trans`.")

    return messages


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
    payload["messages"] = build_messages(payload["modules"], payload["java"], payload["workspace"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not payload["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
