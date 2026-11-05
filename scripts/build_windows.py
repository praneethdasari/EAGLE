"""Automated build and packaging script for EAGLE v0.1.0 on Windows."""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest for a file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def run_cmd(cmd: list[str], description: str) -> None:
    """Run a subprocess command and exit if it fails."""
    print(f"\n[BUILD] {description}...")
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print(
            f"\n[ERROR] {description} failed with exit code {result.returncode}!", file=sys.stderr
        )
        sys.exit(result.returncode)


def main() -> int:
    print("=" * 70)
    print("  EAGLE v0.1.0 — Windows 11 Release Packaging & Build Automation")
    print("=" * 70)

    # 1. Environment checks
    print(f"[INFO] Python executable: {sys.executable}")
    print(f"[INFO] Python version: {sys.version}")
    print(f"[INFO] Platform: {sys.platform}")

    python_exe = sys.executable

    # 2. Run Quality Checks
    run_cmd([python_exe, "-m", "pytest", "tests/unit"], "Running Automated Unit Tests")
    run_cmd([python_exe, "-m", "ruff", "check", "eagle", "tests"], "Checking Code Quality (Ruff)")
    run_cmd([python_exe, "-m", "mypy", "eagle", "tests"], "Checking Static Types (Mypy)")

    # 3. Clean previous build artifacts
    build_dir = ROOT_DIR / "build"
    dist_dir = ROOT_DIR / "dist"
    if build_dir.exists():
        print(f"[INFO] Removing old build directory: {build_dir}")
        shutil.rmtree(build_dir, ignore_errors=True)
    if dist_dir.exists():
        print(f"[INFO] Removing old dist directory: {dist_dir}")
        shutil.rmtree(dist_dir, ignore_errors=True)

    # 4. Invoke PyInstaller
    spec_file = ROOT_DIR / "eagle.spec"
    if not spec_file.exists():
        print(f"[ERROR] Spec file not found at {spec_file}", file=sys.stderr)
        return 1

    run_cmd(
        [python_exe, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
        "Building Standalone Windows Executable via PyInstaller",
    )

    # 5. Verify Build Output
    app_dist = dist_dir / "EAGLE"
    exe_path = app_dist / "EAGLE.exe"
    if not exe_path.exists():
        print(f"[ERROR] Executable not found at expected path: {exe_path}", file=sys.stderr)
        return 1

    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print("\n[SUCCESS] Executable generated successfully:")
    print(f"  Path: {exe_path}")
    print(f"  Size: {size_mb:.2f} MB")

    # 6. Generate Checksums
    exe_hash = compute_sha256(exe_path)
    checksum_file = dist_dir / "SHA256SUMS.txt"
    checksum_content = f"{exe_hash}  EAGLE.exe\n"
    checksum_file.write_text(checksum_content, encoding="utf-8")
    print(f"  SHA-256: {exe_hash}")
    print(f"  Checksums saved to: {checksum_file}")

    print("\n" + "=" * 70)
    print("  EAGLE v0.1.0 Build Complete & Verified!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
