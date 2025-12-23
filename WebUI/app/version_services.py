"""
Extractor Version Management Services.

Provides business logic for managing extractor versions, git tracking, and version queries.
Integrates git utilities with the ExtractorVersion model.
"""

import logging
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.utils import timezone

from .models import ExtractorVersion, Pattern, ProductListing
from .utils.git_utils import (
    get_current_commit_hash,
    get_commit_info,
    get_file_commit_hash,
    is_git_repository,
)

logger = logging.getLogger(__name__)


class VersionService:
    """Service for managing extractor versions and git integration."""

    @staticmethod
    def get_or_create_version(
        extractor_module: str,
        commit_hash: Optional[str] = None,
    ) -> Optional[ExtractorVersion]:
        """
        Get or create an ExtractorVersion for the given module and commit.

        Args:
            extractor_module: Python module name (e.g., "generated_extractors.komplett_no")
            commit_hash: Git commit hash (defaults to current HEAD)

        Returns:
            ExtractorVersion instance, or None if git info unavailable
        """
        # Use provided commit hash or get current HEAD
        if not commit_hash:
            commit_hash = get_current_commit_hash()

        if not commit_hash:
            logger.warning("Could not determine git commit hash")
            return None

        # Check if version already exists
        try:
            version = ExtractorVersion.objects.get(
                commit_hash=commit_hash,
                extractor_module=extractor_module
            )
            logger.debug(f"Found existing version: {version}")
            return version
        except ExtractorVersion.DoesNotExist:
            pass

        # Get commit info
        commit_info = get_commit_info(commit_hash)
        if not commit_info:
            logger.warning(f"Could not get commit info for {commit_hash}")
            # Create minimal version record
            return ExtractorVersion.objects.create(
                commit_hash=commit_hash,
                extractor_module=extractor_module,
            )

        # Create new version with full metadata
        metadata = {
            'branch': commit_info.get('branch'),
            'tags': commit_info.get('tags', []),
        }

        version = ExtractorVersion.objects.create(
            commit_hash=commit_hash,
            extractor_module=extractor_module,
            commit_message=commit_info.get('message', ''),
            commit_author=commit_info.get('author', ''),
            commit_date=commit_info.get('date'),
            metadata=metadata,
        )

        logger.info(f"Created new version: {version}")
        return version

    @staticmethod
    def get_current_version(extractor_module: str) -> Optional[ExtractorVersion]:
        """
        Get or create version for the current git HEAD.

        Args:
            extractor_module: Python module name

        Returns:
            ExtractorVersion for current HEAD, or None if unavailable
        """
        if not is_git_repository():
            logger.warning("Not in a git repository")
            return None

        return VersionService.get_or_create_version(extractor_module)

    @staticmethod
    def get_version_by_hash(commit_hash: str) -> Optional[ExtractorVersion]:
        """
        Get existing version by commit hash (any module).

        Args:
            commit_hash: Git commit SHA

        Returns:
            First ExtractorVersion with this hash, or None
        """
        try:
            return ExtractorVersion.objects.filter(commit_hash=commit_hash).first()
        except ExtractorVersion.DoesNotExist:
            return None

    @staticmethod
    def list_versions_for_module(
        extractor_module: str,
        limit: Optional[int] = None
    ) -> List[ExtractorVersion]:
        """
        List all versions for a specific extractor module.

        Args:
            extractor_module: Python module name
            limit: Optional limit on number of results

        Returns:
            List of ExtractorVersion instances, ordered by creation date (newest first)
        """
        versions = ExtractorVersion.objects.filter(
            extractor_module=extractor_module
        ).order_by('-created_at')

        if limit:
            versions = versions[:limit]

        return list(versions)

    @staticmethod
    def get_latest_version(extractor_module: str) -> Optional[ExtractorVersion]:
        """
        Get the most recently created version for an extractor module.

        Args:
            extractor_module: Python module name

        Returns:
            Latest ExtractorVersion, or None if no versions exist
        """
        return ExtractorVersion.objects.filter(
            extractor_module=extractor_module
        ).order_by('-created_at').first()

    @staticmethod
    def get_version_stats(extractor_module: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about extractor versions.

        Args:
            extractor_module: Optional module to filter stats (None = all modules)

        Returns:
            Dictionary with version statistics
        """
        versions = ExtractorVersion.objects.all()

        if extractor_module:
            versions = versions.filter(extractor_module=extractor_module)

        total_versions = versions.count()

        if extractor_module:
            # Stats for single module
            latest_version = versions.order_by('-created_at').first()
            pattern_count = Pattern.objects.filter(
                extractor_version__extractor_module=extractor_module
            ).count()
            listing_count = ProductListing.objects.filter(
                extractor_version__extractor_module=extractor_module
            ).count()

            return {
                'extractor_module': extractor_module,
                'total_versions': total_versions,
                'latest_version': latest_version,
                'patterns_using_version': pattern_count,
                'listings_using_version': listing_count,
            }
        else:
            # Global stats
            unique_modules = versions.values_list(
                'extractor_module', flat=True
            ).distinct().count()

            return {
                'total_versions': total_versions,
                'unique_modules': unique_modules,
            }

    @staticmethod
    @transaction.atomic
    def update_pattern_version(
        pattern: Pattern,
        extractor_module: Optional[str] = None,
        commit_hash: Optional[str] = None,
    ) -> bool:
        """
        Update a pattern to track the current or specified extractor version.

        Args:
            pattern: Pattern instance to update
            extractor_module: Module name (defaults to pattern.extractor_module)
            commit_hash: Specific commit (defaults to current HEAD)

        Returns:
            True if updated successfully, False otherwise
        """
        module = extractor_module or pattern.extractor_module
        if not module:
            logger.warning(f"No extractor module specified for pattern {pattern.domain}")
            return False

        version = VersionService.get_or_create_version(module, commit_hash)
        if not version:
            logger.warning(f"Could not create version for {module}")
            return False

        pattern.extractor_version = version
        pattern.save(update_fields=['extractor_version', 'updated_at'])

        logger.info(f"Updated pattern {pattern.domain} to version {version}")
        return True

    @staticmethod
    @transaction.atomic
    def update_listing_version(
        listing: ProductListing,
        version: ExtractorVersion,
    ) -> bool:
        """
        Update a product listing to track an extractor version.

        Args:
            listing: ProductListing instance to update
            version: ExtractorVersion to associate

        Returns:
            True if updated successfully, False otherwise
        """
        listing.extractor_version = version
        listing.save(update_fields=['extractor_version', 'updated_at'])

        logger.info(f"Updated listing {listing.url} to version {version}")
        return True

    @staticmethod
    def get_versions_for_commit(commit_hash: str) -> List[ExtractorVersion]:
        """
        Get all extractor versions for a specific commit hash.

        Args:
            commit_hash: Git commit SHA

        Returns:
            List of ExtractorVersion instances
        """
        return list(ExtractorVersion.objects.filter(commit_hash=commit_hash))

    @staticmethod
    def cleanup_orphaned_versions(dry_run: bool = True) -> Dict[str, Any]:
        """
        Find and optionally delete versions not referenced by any patterns or listings.

        Args:
            dry_run: If True, only report what would be deleted (default)

        Returns:
            Dictionary with cleanup statistics
        """
        # Find versions not referenced by patterns or listings
        orphaned = ExtractorVersion.objects.filter(
            patterns__isnull=True,
            listings__isnull=True
        )

        count = orphaned.count()
        orphaned_list = list(orphaned.values('id', 'commit_hash', 'extractor_module'))

        if not dry_run:
            deleted_count, _ = orphaned.delete()
            logger.info(f"Deleted {deleted_count} orphaned versions")
            return {
                'dry_run': False,
                'deleted': deleted_count,
                'orphaned_versions': orphaned_list,
            }

        return {
            'dry_run': True,
            'would_delete': count,
            'orphaned_versions': orphaned_list,
        }
