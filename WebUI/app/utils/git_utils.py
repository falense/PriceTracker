"""
Git utilities for version tracking.
Provides functions to retrieve git commit information for extractor versioning.
"""
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


def get_git_root() -> Optional[Path]:
    """
    Get the root directory of the git repository.

    Returns:
        Path to git root, or None if not in a git repository
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_current_commit_hash() -> Optional[str]:
    """
    Get the current git commit hash (full 40-character SHA).

    Returns:
        Full commit hash, or None if not available
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_commit_info(commit_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a git commit.

    Args:
        commit_hash: Specific commit to query (defaults to HEAD)

    Returns:
        Dictionary with commit info, or None if not available
        Keys: hash, message, author, email, date, branch, tags
    """
    target = commit_hash or 'HEAD'

    try:
        # Get commit hash
        hash_result = subprocess.run(
            ['git', 'rev-parse', target],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        commit_hash = hash_result.stdout.strip()

        # Get commit details using format placeholders
        # %H = full hash, %s = subject, %an = author name, %ae = author email, %ai = author date ISO
        details_result = subprocess.run(
            ['git', 'show', '-s', '--format=%H%n%s%n%an%n%ae%n%ai', commit_hash],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )

        lines = details_result.stdout.strip().split('\n')
        if len(lines) < 5:
            return None

        # Parse commit date
        commit_date = None
        try:
            # Git date format: 2024-01-15 14:30:45 +0100
            commit_date = datetime.fromisoformat(lines[4].replace(' +', '+').replace(' -', '-'))
        except (ValueError, IndexError):
            pass

        # Get current branch
        branch = None
        try:
            branch_result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            branch = branch_result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Get tags pointing to this commit
        tags = []
        try:
            tags_result = subprocess.run(
                ['git', 'tag', '--points-at', commit_hash],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            tags = [tag.strip() for tag in tags_result.stdout.strip().split('\n') if tag.strip()]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return {
            'hash': lines[0],
            'message': lines[1],
            'author': lines[2],
            'email': lines[3],
            'date': commit_date,
            'branch': branch,
            'tags': tags,
        }

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return None


def get_file_commit_hash(file_path: str) -> Optional[str]:
    """
    Get the commit hash of the last commit that modified a specific file.

    Args:
        file_path: Path to the file (relative to git root or absolute)

    Returns:
        Commit hash, or None if not available
    """
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H', '--', file_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        hash_str = result.stdout.strip()
        return hash_str if hash_str else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None


def is_git_repository() -> bool:
    """
    Check if the current directory is inside a git repository.

    Returns:
        True if in a git repository, False otherwise
    """
    return get_git_root() is not None


def get_dirty_status() -> bool:
    """
    Check if the git repository has uncommitted changes.

    Returns:
        True if there are uncommitted changes, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
