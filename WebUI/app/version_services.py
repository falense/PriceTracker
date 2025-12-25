"""
Extractor Version Management Services.

Provides business logic for managing extractor versions, git tracking, and version queries.
Integrates git utilities with the ExtractorVersion model.
"""

import logging
from typing import Optional, List, Dict, Any
from django.db import transaction
from django.utils import timezone

from .models import ExtractorVersion, ProductListing
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
        domain: Optional[str] = None,
        store=None,
        commit_hash: Optional[str] = None,
        set_active: bool = False,
    ) -> Optional[ExtractorVersion]:
        """
        Get or create an ExtractorVersion for the given module and commit.

        Args:
            extractor_module: Python module name (e.g., "generated_extractors.komplett_no")
            domain: Domain this extractor handles (e.g., "komplett.no")
            store: Store model instance (optional)
            commit_hash: Git commit hash (defaults to current HEAD)
            set_active: If True, mark this version as active and deactivate others for this domain

        Returns:
            ExtractorVersion instance, or None if git info unavailable
        """
        # Use provided commit hash or get current HEAD
        if not commit_hash:
            commit_hash = get_current_commit_hash()

        if not commit_hash:
            logger.warning("Could not determine git commit hash")
            return None

        # Check if version already exists for this commit and module
        try:
            version = ExtractorVersion.objects.get(
                commit_hash=commit_hash,
                extractor_module=extractor_module
            )
            logger.debug(f"Found existing version: {version}")

            # Update domain/store if provided and different
            updated = False
            if domain and version.domain != domain:
                version.domain = domain
                updated = True
            if store and version.store != store:
                version.store = store
                updated = True

            if updated:
                version.save()

            # Handle activation if requested
            if set_active and domain and not version.is_active:
                VersionService._set_active_version(version, domain)

            return version
        except ExtractorVersion.DoesNotExist:
            pass

        # Get commit info
        commit_info = get_commit_info(commit_hash)

        # Prepare version data
        version_data = {
            'commit_hash': commit_hash,
            'extractor_module': extractor_module,
            'domain': domain,
            'store': store,
            'is_active': set_active,
        }

        if commit_info:
            metadata = {
                'branch': commit_info.get('branch'),
                'tags': commit_info.get('tags', []),
            }
            version_data.update({
                'commit_message': commit_info.get('message', ''),
                'commit_author': commit_info.get('author', ''),
                'commit_date': commit_info.get('date'),
                'metadata': metadata,
            })
        else:
            logger.warning(f"Could not get commit info for {commit_hash}")

        # If setting as active, deactivate other versions for this domain first
        if set_active and domain:
            ExtractorVersion.objects.filter(
                domain=domain,
                is_active=True
            ).exclude(
                commit_hash=commit_hash,
                extractor_module=extractor_module
            ).update(is_active=False)

        version = ExtractorVersion.objects.create(**version_data)
        logger.info(f"Created new version: {version} (active={set_active})")
        return version

    @staticmethod
    def _set_active_version(version: ExtractorVersion, domain: str):
        """
        Mark a version as active and deactivate all other versions for the domain.

        Args:
            version: The version to activate
            domain: The domain to manage
        """
        # Deactivate all other versions for this domain
        ExtractorVersion.objects.filter(
            domain=domain,
            is_active=True
        ).exclude(id=version.id).update(is_active=False)

        # Activate this version
        if not version.is_active:
            version.is_active = True
            version.save(update_fields=['is_active'])
            logger.info(f"Activated version: {version}")

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
            active_version = versions.filter(is_active=True).first()
            listing_count = ProductListing.objects.filter(
                extractor_version__extractor_module=extractor_module
            ).count()

            return {
                'extractor_module': extractor_module,
                'total_versions': total_versions,
                'latest_version': latest_version,
                'active_version': active_version,
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


class VersionAnalyticsService:
    """Service for version analytics and impact analysis."""

    @staticmethod
    def get_version_adoption_stats() -> Dict[str, Any]:
        """
        Get version adoption metrics across all extractors.

        Returns:
            Dict with version adoption statistics
        """
        from django.db.models import Count

        # Count active extractor versions
        active_versions = ExtractorVersion.objects.filter(is_active=True).count()
        total_versions = ExtractorVersion.objects.count()

        # Count listings per version
        listing_versions = ProductListing.objects.exclude(
            extractor_version__isnull=True
        ).values(
            'extractor_version__extractor_module',
            'extractor_version__commit_hash'
        ).annotate(
            listing_count=Count('id')
        ).order_by('-listing_count')

        # Get total counts
        total_listings = ProductListing.objects.count()
        listings_with_version = ProductListing.objects.exclude(extractor_version__isnull=True).count()

        return {
            'total_extractors': active_versions,
            'total_versions': total_versions,
            'active_rate': (active_versions / total_versions * 100) if total_versions > 0 else 0,

            'total_listings': total_listings,
            'listings_with_version': listings_with_version,
            'listings_without_version': total_listings - listings_with_version,
            'listing_version_rate': (listings_with_version / total_listings * 100) if total_listings > 0 else 0,

            'top_listing_versions': list(listing_versions[:10]),
        }

    @staticmethod
    def get_version_impact_analysis(extractor_module: str) -> Dict[str, Any]:
        """
        Analyze impact of version changes on success rates.

        Args:
            extractor_module: Module to analyze

        Returns:
            Dict with version impact metrics
        """
        versions = ExtractorVersion.objects.filter(
            extractor_module=extractor_module
        ).order_by('created_at')

        if not versions.exists():
            return {
                'extractor_module': extractor_module,
                'error': 'No versions found'
            }

        # Get patterns using each version and their success rates
        version_impacts = []
        for version in versions:
            patterns = version.patterns.all()

            if patterns.exists():
                avg_success_rate = sum(p.success_rate for p in patterns) / len(patterns)
                total_attempts = sum(p.total_attempts for p in patterns)

                # PatternHistory was removed - historical tracking now via ExtractorVersion
                avg_historical_rate = None

                version_impacts.append({
                    'version': version,
                    'commit_short': version.commit_hash[:8],
                    'commit_date': version.commit_date,
                    'pattern_count': len(patterns),
                    'current_avg_success_rate': avg_success_rate,
                    'historical_avg_success_rate': avg_historical_rate,
                    'total_attempts': total_attempts,
                })

        return {
            'extractor_module': extractor_module,
            'total_versions': len(versions),
            'version_impacts': version_impacts,
        }

    @staticmethod
    def get_pattern_health_trends(domain: str, days: int = 30) -> Dict[str, Any]:
        """
        Get pattern health trends over time from history.

        Args:
            domain: Pattern domain
            days: Number of days to analyze

        Returns:
            Dict with health trend data
        """
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)

        # PatternHistory was removed - return empty trend data
        return {
            'domain': domain,
            'error': 'PatternHistory model removed - use ExtractorVersion for tracking'
        }

    @staticmethod
    def get_module_usage_stats() -> Dict[str, Any]:
        """
        Get statistics on extractor module usage.

        Returns:
            Dict with module usage statistics
        """
        from django.db.models import Count

        # Count active extractors per module
        module_stats = ExtractorVersion.objects.filter(
            is_active=True
        ).exclude(
            extractor_module__isnull=True
        ).values('extractor_module').annotate(
            count=Count('id')
        ).order_by('-count')

        # Count version diversity per module
        version_diversity = ExtractorVersion.objects.values(
            'extractor_module'
        ).annotate(
            version_count=Count('id')
        ).order_by('-version_count')

        return {
            'total_modules': ExtractorVersion.objects.filter(is_active=True).exclude(extractor_module__isnull=True).values('extractor_module').distinct().count(),
            'module_usage': list(module_stats),
            'version_diversity': list(version_diversity),
        }

    @staticmethod
    def get_user_contribution_stats(days: int = 30) -> Dict[str, Any]:
        """
        Track user contributions to pattern changes.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with user contribution statistics
        """
        from datetime import timedelta
        from django.db.models import Count

        since = timezone.now() - timedelta(days=days)

        # PatternHistory was removed - return empty stats
        return {
            'days_analyzed': days,
            'total_changes': 0,
            'top_contributors': [],
            'change_type_breakdown': [],
            'note': 'PatternHistory model removed - use ExtractorVersion for tracking'
        }
