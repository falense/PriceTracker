#!/usr/bin/env python3
"""
Generate versions.json manifest for extractor modules.

This script scans all extractors in ExtractorPatternAgent/generated_extractors/
and captures git version information for each module. The manifest is used
by PriceFetcher to track which version of each extractor was used.

Usage:
    python scripts/generate_versions_manifest.py
    python scripts/generate_versions_manifest.py --verify  # Check if manifest is current
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def get_repo_root() -> Path:
    """Get the root directory of the git repository."""
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
        # Fallback: assume script is in scripts/ directory
        return Path(__file__).parent.parent


def get_last_commit_for_file(file_path: Path, repo_root: Path) -> Optional[Dict[str, Any]]:
    """
    Get the last commit that modified a specific file.

    Args:
        file_path: Absolute path to the file
        repo_root: Root directory of the git repository

    Returns:
        Dictionary with commit info, or None if not available
    """
    # Make path relative to repo root for git
    try:
        rel_path = file_path.relative_to(repo_root)
    except ValueError:
        print(f"Warning: {file_path} is not in repo {repo_root}", file=sys.stderr)
        return None

    try:
        # Get commit hash for this file
        hash_result = subprocess.run(
            ['git', 'log', '-1', '--pretty=format:%H', '--', str(rel_path)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            cwd=repo_root
        )
        commit_hash = hash_result.stdout.strip()

        if not commit_hash:
            print(f"Warning: No git history found for {rel_path}", file=sys.stderr)
            return None

        # Get commit details
        details_result = subprocess.run(
            ['git', 'show', '-s', '--format=%H%n%h%n%s%n%an%n%ae%n%ai', commit_hash],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            cwd=repo_root
        )

        lines = details_result.stdout.strip().split('\n')
        if len(lines) < 6:
            return None

        # Parse commit date
        try:
            commit_date = datetime.fromisoformat(lines[5].replace(' +', '+').replace(' -', '-'))
            commit_date_str = commit_date.isoformat()
        except (ValueError, IndexError):
            commit_date_str = lines[5] if len(lines) > 5 else None

        return {
            'commit_hash': lines[0],          # Full hash
            'commit_hash_short': lines[1],    # Short hash
            'commit_message': lines[2],
            'commit_author': lines[3],
            'commit_email': lines[4],
            'commit_date': commit_date_str,
        }

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Failed to get git info for {rel_path}: {e}", file=sys.stderr)
        return None


def load_extractor_metadata(module_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load PATTERN_METADATA from an extractor module by parsing the AST.

    This avoids importing the module (which may have dependencies not installed)
    and instead parses the Python file to extract the PATTERN_METADATA dict.

    Args:
        module_path: Path to the extractor Python file

    Returns:
        PATTERN_METADATA dict, or None if not found
    """
    import ast

    try:
        with open(module_path) as f:
            tree = ast.parse(f.read(), filename=str(module_path))

        # Find PATTERN_METADATA assignment
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == 'PATTERN_METADATA':
                        # Evaluate the dict literal
                        if isinstance(node.value, ast.Dict):
                            metadata = {}
                            for key, value in zip(node.value.keys, node.value.values):
                                # Extract key (should be a string constant)
                                if isinstance(key, ast.Constant):
                                    key_str = key.value
                                elif isinstance(key, ast.Str):  # Python < 3.8
                                    key_str = key.s
                                else:
                                    continue

                                # Extract value (support constants, lists, dicts)
                                try:
                                    value_obj = ast.literal_eval(value)
                                    metadata[key_str] = value_obj
                                except (ValueError, TypeError):
                                    # Skip complex values we can't evaluate
                                    pass

                            return metadata

        print(f"Warning: {module_path.name} has no PATTERN_METADATA", file=sys.stderr)
        return None

    except Exception as e:
        print(f"Warning: Failed to parse {module_path.name}: {e}", file=sys.stderr)
        return None


def generate_manifest(repo_root: Path, extractors_dir: Path) -> Dict[str, Dict[str, Any]]:
    """
    Generate version manifest for all extractors.

    Args:
        repo_root: Root of git repository
        extractors_dir: Directory containing extractor modules

    Returns:
        Dictionary mapping module name to version info
    """
    manifest = {}

    # Find all extractor modules (exclude __init__.py, _base.py, etc.)
    extractor_files = sorted(extractors_dir.glob('*.py'))
    extractor_files = [f for f in extractor_files if not f.stem.startswith('_')]

    print(f"Found {len(extractor_files)} extractor modules")

    for extractor_file in extractor_files:
        module_name = extractor_file.stem
        print(f"Processing {module_name}...", end=' ')

        # Load metadata from module
        metadata = load_extractor_metadata(extractor_file)
        if not metadata:
            print("SKIP (no metadata)")
            continue

        # Get git info for this file
        git_info = get_last_commit_for_file(extractor_file, repo_root)

        # Combine metadata and git info
        version_info = {
            'module': module_name,
            'domain': metadata.get('domain', 'unknown'),
            'version': metadata.get('version', 'unknown'),
            'generated_at': metadata.get('generated_at'),
            'confidence': metadata.get('confidence'),
        }

        if git_info:
            version_info.update(git_info)
            print(f"OK (commit: {git_info['commit_hash_short']})")
        else:
            print("OK (no git info)")

        manifest[module_name] = version_info

    return manifest


def verify_manifest(repo_root: Path, extractors_dir: Path, manifest_path: Path) -> bool:
    """
    Verify that the manifest is up-to-date.

    Returns:
        True if manifest is current, False if stale or missing
    """
    if not manifest_path.exists():
        print("ERROR: versions.json does not exist", file=sys.stderr)
        return False

    # Load existing manifest
    with open(manifest_path) as f:
        existing_manifest = json.load(f)

    # Generate fresh manifest
    fresh_manifest = generate_manifest(repo_root, extractors_dir)

    # Compare
    if existing_manifest != fresh_manifest:
        print("ERROR: versions.json is stale", file=sys.stderr)
        print("\nDifferences found:", file=sys.stderr)

        all_modules = set(existing_manifest.keys()) | set(fresh_manifest.keys())
        for module in sorted(all_modules):
            old = existing_manifest.get(module, {})
            new = fresh_manifest.get(module, {})

            if old != new:
                print(f"\n  {module}:", file=sys.stderr)
                if not old:
                    print(f"    Added (commit: {new.get('commit_hash_short', 'N/A')})", file=sys.stderr)
                elif not new:
                    print(f"    Removed", file=sys.stderr)
                else:
                    old_commit = old.get('commit_hash_short', 'N/A')
                    new_commit = new.get('commit_hash_short', 'N/A')
                    if old_commit != new_commit:
                        print(f"    Commit changed: {old_commit} → {new_commit}", file=sys.stderr)
                    if old.get('version') != new.get('version'):
                        print(f"    Version changed: {old.get('version')} → {new.get('version')}", file=sys.stderr)

        print("\nRun: python scripts/generate_versions_manifest.py", file=sys.stderr)
        return False

    print("✓ versions.json is up-to-date")
    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate extractor versions manifest')
    parser.add_argument('--verify', action='store_true', help='Verify manifest is current')
    parser.add_argument('--output', type=Path, help='Output path (default: auto-detect)')
    args = parser.parse_args()

    # Detect paths
    repo_root = get_repo_root()
    extractors_dir = repo_root / 'ExtractorPatternAgent' / 'generated_extractors'
    manifest_path = args.output or (extractors_dir / 'versions.json')

    if not extractors_dir.exists():
        print(f"ERROR: Extractors directory not found: {extractors_dir}", file=sys.stderr)
        sys.exit(1)

    # Verify mode
    if args.verify:
        success = verify_manifest(repo_root, extractors_dir, manifest_path)
        sys.exit(0 if success else 1)

    # Generate mode
    print(f"Generating versions manifest...")
    print(f"  Repo root: {repo_root}")
    print(f"  Extractors: {extractors_dir}")
    print(f"  Output: {manifest_path}")
    print()

    manifest = generate_manifest(repo_root, extractors_dir)

    # Write manifest
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"\n✓ Generated manifest with {len(manifest)} extractors")
    print(f"  Written to: {manifest_path}")


if __name__ == '__main__':
    main()
