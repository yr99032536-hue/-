#!/usr/bin/env python3
"""Cross-platform installer for paper-translate.

Usage:
    python install.py --vault "/path/to/Obsidian Vault"

Works on Windows, Linux, and macOS.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SCRIPT_DIR.parent
DEFAULT_VAULT = PLUGIN_DIR.parent.parent
IS_WIN = platform.system() == "Windows"


def python_in_venv(venv_dir: Path) -> Path:
    """Return the Python executable path inside the virtual environment."""
    if IS_WIN:
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def pip_in_venv(venv_dir: Path) -> Path:
    """Return the pip executable path inside the virtual environment."""
    if IS_WIN:
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def create_venv(venv_dir: Path, bootstrap_python: str) -> Path:
    """Create (or reuse) a virtual environment with --system-site-packages."""
    python = python_in_venv(venv_dir)
    cfg = venv_dir / "pyvenv.cfg"

    if python.exists() and cfg.exists():
        text = cfg.read_text(encoding="utf-8", errors="ignore")
        if "include-system-site-packages = true" in text:
            print(f"[paper-translate] 기존 가상환경 재사용: {venv_dir}")
            return python

    print(f"[paper-translate] 가상환경 생성: {venv_dir}")
    subprocess.run(
        [bootstrap_python, "-m", "venv", "--clear", "--copies", "--system-site-packages", str(venv_dir)],
        check=True,
    )
    return python


def install_deps(venv_dir: Path, requirements: Path) -> None:
    """Install Python dependencies from requirements.txt."""
    pip = pip_in_venv(venv_dir)
    print(f"[paper-translate] pip: {pip}")
    subprocess.run(
        [str(pip), "install", "-r", str(requirements)],
        check=True,
    )


def check_java() -> dict:
    """Check Java availability. Returns {ok, path, version}."""
    java = shutil.which("java")
    if not java:
        return {"ok": False, "path": None, "version": None}

    result = subprocess.run(
        [java, "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stderr or result.stdout) or ""
    version = output.splitlines()[0] if output else ""
    return {"ok": result.returncode == 0, "path": java, "version": version}


def java_install_hint() -> str:
    """Return platform-appropriate Java install instructions."""
    if IS_WIN:
        return (
            "Java가 없습니다. 다음 중 하나로 설치하세요:\n"
            "  - winget install Microsoft.OpenJDK.21\n"
            "  - https://adoptium.net/ 에서 다운로드\n"
            "  설치 후 터미널을 다시 열어주세요."
        )
    return (
        "Java가 없습니다. 다음 중 하나로 설치하세요:\n"
        "  - bash scripts/install.sh --vault <vault> --install-java  (apt 전용)\n"
        "  - sudo apt install openjdk-21-jdk\n"
        "  - brew install openjdk\n"
        "  - https://adoptium.net/ 에서 다운로드"
    )


def run_setup(venv_python: Path, vault: Path) -> None:
    """Run setup_workspace.py to create workspace folders."""
    setup_script = SCRIPT_DIR / "setup_workspace.py"
    subprocess.run(
        [str(venv_python), str(setup_script), "--vault", str(vault)],
        check=True,
    )


def run_check(venv_python: Path, vault: Path) -> None:
    """Run check_environment.py to verify the setup."""
    check_script = SCRIPT_DIR / "check_environment.py"
    subprocess.run(
        [str(venv_python), str(check_script), "--vault", str(vault)],
        check=False,
    )


def main():
    parser = argparse.ArgumentParser(
        description="paper-translate 크로스 플랫폼 설치 스크립트",
        usage="python install.py [--vault /path/to/ObsidianVault]",
    )
    parser.add_argument(
        "--vault",
        default=str(DEFAULT_VAULT),
        help="Obsidian 볼트 루트 경로 (기본: 플러그인 상위 디렉토리)",
    )
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    requirements = PLUGIN_DIR / "requirements.txt"
    tag = os.environ.get("USER", "default")
    venv_env = os.environ.get("PAPER_TRANSLATE_VENV")
    venv_dir = Path(venv_env) if venv_env else Path(tempfile.gettempdir()) / f"paper-translate-venv-{tag}"

    print(f"[paper-translate] 플러그인: {PLUGIN_DIR}")
    print(f"[paper-translate] 볼트:     {vault}")
    print(f"[paper-translate] 플랫폼:   {platform.system()} ({platform.machine()})")

    if not requirements.exists():
        print(f"requirements.txt 없음: {requirements}", file=sys.stderr)
        sys.exit(1)

    # 1. 가상환경
    venv_python = create_venv(venv_dir, sys.executable)
    print(f"[paper-translate] python:  {venv_python}")

    # 2. 의존성 설치
    install_deps(venv_dir, requirements)

    # 3. Java 확인
    java = check_java()
    if java["ok"]:
        print(f"[paper-translate] java:    {java['path']} ({java['version']})")
    else:
        print(java_install_hint())
        sys.exit(1)

    # 4. 워크스페이스 폴더 생성
    run_setup(venv_python, vault)

    # 5. 환경 점검
    run_check(venv_python, vault)

    print()
    print("[paper-translate] 설치 완료!")
    print(f"  1. PDF를 넣으세요:  {vault / '논문' / 'pdf'}")
    print("  2. /paper-translate 실행")


if __name__ == "__main__":
    main()
