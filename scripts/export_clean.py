#!/usr/bin/env python3
"""Clean Snapshot Export & Repository Sanitization Pipeline.

Automates the extraction of clean code, tests, and feature documentation from the
private development repository into the secondary local repository
(~/github/beattidp/ancestry-org-genealogy) on branch 'trunk' for public GitHub release.

Features:
- Whitelist-based file copying (excludes internal worklogs, plans, and session transcripts).
- Automated pattern redaction (replaces private identifiers with ABCD-123 and generic placeholders).
- Automated security guard (fails immediately if any sensitive pattern is detected in destination).
- Git branch management (ensures branch 'trunk' is checked out and cleanly committed).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Sensitive regex patterns to redact
DEFAULT_REPLACEMENTS = [
    (re.compile(r"cis\.user\.MM9W-QYW8"), "cis.user.SAMPLE-USER"),
    (re.compile(r"MM9W-QYW8"), "SAMPLE-USER"),
    (re.compile(r"KWHS-6NN"), "ABCD-123"),
    (re.compile(r"Douglas Paul Beattie Jr"), "Sample User"),
    (re.compile(r"Douglas Beattie Jr"), "Sample User"),
    (re.compile(r"John Chandler Beattie"), "Sample Ancestor"),
]

# Forbidden patterns checked by the security guard in the target tree
FORBIDDEN_PATTERNS = [
    re.compile(r"MM9W", re.IGNORECASE),
    re.compile(r"Beattie", re.IGNORECASE),
    re.compile(r"KWHS", re.IGNORECASE),
]

# Explicit files to copy from root
ROOT_FILES = [
    "README.md",
    "requirements.txt",
    "pytest.ini",
    ".python-version",
    ".env.example",
    ".gitignore",
    "audit_sources.py",
    "ingest.py",
    "probe.py",
    "tree_summary.py",
    "validate_tree.py",
]

# Explicit directories to copy
DIRECTORIES = [
    "src",
    "tests",
    "doc/features",
]

# File extensions treated as text for redaction
TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".env",
    ".example",
    ".sh",
}


def run_cmd(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command and return result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def sanitize_content(content: str) -> str:
    """Apply replacement patterns to text content."""
    for pattern, replacement in DEFAULT_REPLACEMENTS:
        content = pattern.sub(replacement, content)
    return content


def copy_and_sanitize_file(src_file: Path, dst_file: Path) -> None:
    """Copy a file from src to dst, applying sanitization if it's a text file."""
    dst_file.parent.mkdir(parents=True, exist_ok=True)

    if src_file.suffix in TEXT_EXTENSIONS or src_file.name in ROOT_FILES:
        try:
            content = src_file.read_text(encoding="utf-8")
            sanitized = sanitize_content(content)
            dst_file.write_text(sanitized, encoding="utf-8")
            return
        except UnicodeDecodeError:
            pass  # Fall back to binary copy if not UTF-8

    shutil.copy2(src_file, dst_file)


def run_security_guard(target_dir: Path) -> list[str]:
    """Scan all files in the target directory for forbidden patterns."""
    violations: list[str] = []

    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        # Skip git internal files
        if ".git" in path.parts:
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    rel_path = path.relative_to(target_dir)
                    violations.append(
                        f"[{pattern.pattern}] {rel_path}:{line_num}: {line.strip()}"
                    )

    return violations


def export_clean_snapshot(
    source_dir: Path,
    target_dir: Path,
    branch: str = "trunk",
    commit: bool = True,
) -> None:
    """Perform the clean snapshot export."""
    print("=" * 60)
    print("Ancestry Genealogy - Clean Release Snapshot Pipeline")
    print("=" * 60)
    print(f"Source Directory: {source_dir}")
    print(f"Target Directory: {target_dir}")
    print(f"Target Branch:    {branch}")

    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    git_dir = target_dir / ".git"
    if not git_dir.exists():
        print(f"Initializing git repository in {target_dir}...")
        run_cmd(["git", "init"], cwd=target_dir)

    # 1. Clean out existing tracked files in target (except .git)
    print("\n[Step 1/5] Synchronizing file tree...")
    for item in target_dir.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 2. Copy root files
    print("\n[Step 2/5] Copying and sanitizing root files...")
    for filename in ROOT_FILES:
        src = source_dir / filename
        if src.exists():
            dst = target_dir / filename
            copy_and_sanitize_file(src, dst)
            print(f"  + {filename}")
        else:
            print(f"  - {filename} (not found, skipped)")

    # 3. Copy directories
    print("\n[Step 3/5] Copying and sanitizing directory trees...")
    for dir_rel in DIRECTORIES:
        src_dir = source_dir / dir_rel
        if not src_dir.exists():
            continue
        print(f"  Directory: {dir_rel}/")
        for src_path in src_dir.rglob("*"):
            if not src_path.is_file():
                continue
            if "__pycache__" in src_path.parts or ".pytest_cache" in src_path.parts:
                continue
            rel_path = src_path.relative_to(source_dir)
            dst_path = target_dir / rel_path
            copy_and_sanitize_file(src_path, dst_path)

    # 4. Security Guard Validation
    print("\n[Step 4/5] Running Security Guard verification scan...")
    violations = run_security_guard(target_dir)
    if violations:
        print("\n" + "!" * 60)
        print("SECURITY GUARD VIOLATION: Sensitive patterns detected!")
        print("!" * 60)
        for v in violations:
            print(f"  {v}")
        print("\nAborting clean export. Destination repository has NOT been committed.")
        sys.exit(1)

    print("  [PASS] Zero sensitive patterns found in exported tree.")

    # 5. Git Commit & Branch Management
    print(f"\n[Step 5/5] Managing git branch '{branch}' in target repository...")
    # Check current branch
    branch_proc = run_cmd(["git", "branch", "--show-current"], cwd=target_dir)
    current_branch = branch_proc.stdout.strip()

    if current_branch != branch:
        # Check if branch exists
        check_proc = run_cmd(["git", "rev-parse", "--verify", branch], cwd=target_dir)
        if check_proc.returncode == 0:
            run_cmd(["git", "checkout", branch], cwd=target_dir)
        else:
            run_cmd(["git", "checkout", "-B", branch], cwd=target_dir)

    # Ensure git user config exists in target repository
    target_name = run_cmd(["git", "config", "user.name"], cwd=target_dir).stdout.strip()
    target_email = run_cmd(["git", "config", "user.email"], cwd=target_dir).stdout.strip()
    if not target_name:
        src_name = run_cmd(["git", "config", "user.name"], cwd=source_dir).stdout.strip() or "beattidp"
        run_cmd(["git", "config", "user.name", src_name], cwd=target_dir)
    if not target_email:
        src_email = run_cmd(["git", "config", "user.email"], cwd=source_dir).stdout.strip() or "5289980+beattidp@users.noreply.github.com"
        run_cmd(["git", "config", "user.email", src_email], cwd=target_dir)

    # Stage changes
    run_cmd(["git", "add", "-A"], cwd=target_dir)

    status_proc = run_cmd(["git", "status", "--porcelain"], cwd=target_dir)
    if not status_proc.stdout.strip():
        print("  Target repository is already up to date (no changes to commit).")
    elif commit:
        # Determine latest tag or version from source repo
        tag_proc = run_cmd(["git", "describe", "--tags", "--always"], cwd=source_dir)
        version_label = tag_proc.stdout.strip() if tag_proc.returncode == 0 else "latest"
        commit_msg = (
            f"chore(release): export clean snapshot {version_label}\n\n"
            "Sanitized public release tree:\n"
            "- Core pedigree ingestion and SQLite database\n"
            "- Deterministic biological & chronological constraint validation engine\n"
            "- Source citation tier classification and completeness auditor\n"
            "- Automated redactions (ABCD-123 root dummy PID)\n"
            "- Full unit test suite"
        )
        commit_proc = run_cmd(["git", "commit", "-m", commit_msg], cwd=target_dir)
        if commit_proc.returncode == 0:
            print("  [SUCCESS] Created clean release commit on branch 'trunk':")
            log_proc = run_cmd(["git", "log", "-n", "1", "--oneline"], cwd=target_dir)
            print(f"    {log_proc.stdout.strip()}")
        else:
            print(f"  Git commit stderr: {commit_proc.stderr}")

    print("\n" + "=" * 60)
    print("Clean export completed successfully!")
    print(f"Target repository is ready at: {target_dir}")
    print(f"Branch: {branch}")
    print("To push to GitHub:")
    print(f"  cd {target_dir}")
    print(f"  git push -u origin {branch}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export sanitized release snapshot to secondary local repository."
    )
    default_target = Path(
        os.environ.get(
            "EXPORT_TARGET_DIR",
            str(Path.home() / "github" / "beattidp" / "ancestry-org-genealogy"),
        )
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Source repository directory (default: parent of script directory).",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=default_target,
        help=f"Target secondary repository directory (default: {default_target}).",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="trunk",
        help="Target git branch name (default: trunk).",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Stage files only without creating a git commit.",
    )
    args = parser.parse_args()

    export_clean_snapshot(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
        branch=args.branch,
        commit=not args.no_commit,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
