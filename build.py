"""
CryNet Windows Executable Build Script
Packages CryNet into a self-contained offline desktop application using PyInstaller.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"


def verify_mediapipe_compatibility() -> None:
    """Prevent packaging a build with MediaPipe 1.x, which lacks mp.solutions.hands."""
    try:
        import mediapipe as mp
        version = getattr(mp, "__version__", "unknown")
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "hands"):
            raise RuntimeError(
                f"Incompatible MediaPipe {version}. CryNet requires MediaPipe 0.10.21 "
                "for the mp.solutions.hands API. Install requirements.txt first."
            )
        print(f"MediaPipe compatibility check: OK ({version})")
    except Exception as exc:
        print(f"MediaPipe compatibility check FAILED: {exc}")
        sys.exit(2)


def build_windows_executable():
    verify_mediapipe_compatibility()
    print("=" * 60)
    print("Building CryNet Windows Standalone Package")
    print("=" * 60)

    # Clean previous build artifacts
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    spec_name = "CryNet"

    # PyInstaller arguments
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",                 # No console window for production
        f"--name={spec_name}",
        "--add-data=config;config",
        "--collect-all=mediapipe",
        "--collect-all=cv2",
        "--collect-all=PySide6",
        "--collect-submodules=pynput",
        str(BASE_DIR / "main.py"),
    ]

    print(f"Running command:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode == 0:
        print("\n" + "=" * 60)
        print("BUILD SUCCESSFUL!")
        print(f"Binary directory: {DIST_DIR / spec_name}")
        print(f"Executable:       {DIST_DIR / spec_name / 'CryNet.exe'}")
        print("=" * 60)
    else:
        print(f"\nBUILD FAILED with return code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == "__main__":
    build_windows_executable()
