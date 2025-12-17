"""
Pattern Management Services.

Provides business logic for pattern management, testing, validation, and history tracking.
Supports both legacy JSON patterns and new Python extractor modules.
"""
import json
import subprocess
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from urllib.parse import urlparse

from django.utils import timezone
from django.db.models import Max, Q
from django.core.cache import cache

from .models import Pattern, PatternHistory, ProductListing, Store

logger = logging.getLogger(__name__)

# Add ExtractorPatternAgent to path for generated_extractors import
REPO_ROOT = Path(__file__).parent.parent.parent
EXTRACTOR_PATH = REPO_ROOT / 'ExtractorPatternAgent'
if str(EXTRACTOR_PATH) not in sys.path:
    sys.path.insert(0, str(EXTRACTOR_PATH))


class PatternManagementService:
    """Service for managing patterns (CRUD operations)."""

    @staticmethod
    def get_all_patterns(with_stats=True) -> Dict[str, Any]:
        """
        Get all patterns with optional statistics.

        Args:
            with_stats: Whether to include health statistics

        Returns:
            Dict with patterns list and stats
        """
        patterns = Pattern.objects.all().select_related('store').order_by('domain')

        if not with_stats:
            return {'patterns': patterns, 'stats': None}

        # Calculate statistics
        total = patterns.count()
        healthy = patterns.filter(success_rate__gte=0.8).count()
        warning = patterns.filter(
            success_rate__gte=0.6,
            success_rate__lt=0.8
        ).count()
        failing = patterns.filter(success_rate__lt=0.6).count()
        pending = patterns.filter(total_attempts=0).count()

        stats = {
            'total': total,
            'healthy': healthy,
            'warning': warning,
            'failing': failing,
            'pending': pending
        }

        return {'patterns': patterns, 'stats': stats}

    @staticmethod
    def get_pattern_detail(domain: str) -> Optional[Pattern]:
        """
        Get single pattern by domain.

        Args:
            domain: Pattern domain

        Returns:
            Pattern instance or None
        """
        try:
            return Pattern.objects.select_related('store').prefetch_related(
                'history'
            ).get(domain=domain)
        except Pattern.DoesNotExist:
            return None

    @staticmethod
    def create_pattern(
        domain: str,
        extractor_module: str,
        user,
        change_reason: str = 'Initial creation'
    ) -> Tuple[Pattern, bool]:
        """
        Create new pattern with Python extractor.

        Args:
            domain: Pattern domain
            extractor_module: Python extractor module name (e.g., "komplett_no")
            user: User creating the pattern
            change_reason: Reason for creation

        Returns:
            Tuple of (Pattern, created)
        """
        # Normalize domain
        domain = domain.lower().strip()
        if domain.startswith('www.'):
            domain = domain[4:]

        # Get or create store
        store, _ = Store.objects.get_or_create(
            domain=domain,
            defaults={'name': domain.split('.')[0].title()}
        )

        # Create pattern
        pattern, created = Pattern.objects.update_or_create(
            domain=domain,
            defaults={
                'extractor_module': extractor_module,
                'pattern_json': None,  # No longer using JSON
                'store': store,
                'last_validated': timezone.now()
            }
        )

        # PatternHistory now stores Python module reference instead of JSON
        # (We may need to update PatternHistory model later to handle Python code)

        return pattern, created

    @staticmethod
    def update_pattern(
        domain: str,
        extractor_module: str,
        user,
        change_reason: str = 'Manual edit'
    ) -> Pattern:
        """
        Update existing pattern's extractor module.

        Args:
            domain: Pattern domain
            extractor_module: New extractor module name
            user: User making the update
            change_reason: Reason for update

        Returns:
            Updated Pattern instance
        """
        pattern = Pattern.objects.get(domain=domain)

        # Update pattern
        pattern.extractor_module = extractor_module
        pattern.pattern_json = None  # Clear JSON pattern
        pattern.last_validated = timezone.now()
        pattern.save(update_fields=['extractor_module', 'pattern_json', 'last_validated', 'updated_at'])

        return pattern

    @staticmethod
    def delete_pattern(domain: str) -> bool:
        """
        Delete pattern (hard delete).

        Args:
            domain: Pattern domain

        Returns:
            True if deleted, False if not found
        """
        try:
            pattern = Pattern.objects.get(domain=domain)
            pattern.delete()
            return True
        except Pattern.DoesNotExist:
            return False

    @staticmethod
    def rollback_pattern(
        domain: str,
        version_number: int,
        user,
        change_reason: str = None
    ) -> Pattern:
        """
        Rollback pattern to previous version.

        Args:
            domain: Pattern domain
            version_number: Version to rollback to
            user: User performing rollback
            change_reason: Optional reason

        Returns:
            Updated Pattern instance
        """
        pattern = Pattern.objects.get(domain=domain)
        history_version = PatternHistory.objects.get(
            pattern=pattern,
            version_number=version_number
        )

        if not change_reason:
            change_reason = f'Rollback to version {version_number}'

        # Save current state before rollback
        last_version = PatternHistory.objects.filter(
            pattern=pattern
        ).aggregate(Max('version_number'))['version_number__max']

        next_version = (last_version or 0) + 1

        PatternHistory.objects.create(
            pattern=pattern,
            domain=pattern.domain,
            version_number=next_version,
            pattern_json=pattern.pattern_json,
            changed_by=user,
            change_reason=f'Before rollback to version {version_number}',
            change_type='auto_save',
            success_rate_at_time=pattern.success_rate,
            total_attempts_at_time=pattern.total_attempts
        )

        # Rollback to old version
        pattern.pattern_json = history_version.pattern_json
        pattern.last_validated = timezone.now()
        # Reset success metrics to re-evaluate
        pattern.success_rate = 0.0
        pattern.total_attempts = 0
        pattern.successful_attempts = 0
        pattern.save()

        # Create rollback history entry
        next_version += 1
        PatternHistory.objects.create(
            pattern=pattern,
            domain=pattern.domain,
            version_number=next_version,
            pattern_json=history_version.pattern_json,
            changed_by=user,
            change_reason=change_reason,
            change_type='rollback',
            success_rate_at_time=0.0,
            total_attempts_at_time=0
        )

        return pattern


class PatternHistoryService:
    """Service for pattern history and comparison."""

    @staticmethod
    def get_pattern_history(domain: str, limit: int = 50) -> List[PatternHistory]:
        """
        Get pattern version history.

        Args:
            domain: Pattern domain
            limit: Max versions to return

        Returns:
            List of PatternHistory instances
        """
        return PatternHistory.objects.filter(
            domain=domain
        ).select_related('pattern', 'changed_by').order_by('-version_number')[:limit]

    @staticmethod
    def get_pattern_version(domain: str, version_number: int) -> Optional[PatternHistory]:
        """
        Get specific pattern version.

        Args:
            domain: Pattern domain
            version_number: Version number

        Returns:
            PatternHistory instance or None
        """
        try:
            return PatternHistory.objects.get(
                domain=domain,
                version_number=version_number
            )
        except PatternHistory.DoesNotExist:
            return None

    @staticmethod
    def compare_versions(
        version1_json: Dict,
        version2_json: Dict
    ) -> Dict[str, Any]:
        """
        Generate diff between two pattern versions.

        Args:
            version1_json: First pattern JSON
            version2_json: Second pattern JSON

        Returns:
            Dict with added/removed/modified fields and details
        """
        diff = {
            'added_fields': [],
            'removed_fields': [],
            'modified_fields': [],
            'details': {},
            'metadata_changes': {}
        }

        patterns1 = version1_json.get('patterns', {})
        patterns2 = version2_json.get('patterns', {})

        # Find added/removed fields
        fields1 = set(patterns1.keys())
        fields2 = set(patterns2.keys())

        diff['added_fields'] = list(fields2 - fields1)
        diff['removed_fields'] = list(fields1 - fields2)

        # Find modified fields
        for field in fields1 & fields2:
            if patterns1[field] != patterns2[field]:
                diff['modified_fields'].append(field)
                diff['details'][field] = {
                    'old': patterns1[field],
                    'new': patterns2[field],
                    'changes': PatternHistoryService._compare_field_pattern(
                        patterns1[field],
                        patterns2[field]
                    )
                }

        # Compare metadata
        metadata1 = version1_json.get('metadata', {})
        metadata2 = version2_json.get('metadata', {})
        if metadata1 != metadata2:
            diff['metadata_changes'] = {
                'old': metadata1,
                'new': metadata2
            }

        return diff

    @staticmethod
    def _compare_field_pattern(field1: Dict, field2: Dict) -> Dict[str, str]:
        """Compare individual field patterns."""
        changes = {}

        # Compare primary selector
        if field1.get('primary') != field2.get('primary'):
            changes['primary'] = 'Modified'

        # Compare fallbacks
        fallbacks1 = field1.get('fallbacks', [])
        fallbacks2 = field2.get('fallbacks', [])

        if len(fallbacks1) != len(fallbacks2):
            changes['fallbacks_count'] = f'{len(fallbacks1)} → {len(fallbacks2)}'
        elif fallbacks1 != fallbacks2:
            changes['fallbacks'] = 'Modified'

        return changes


class PatternTestService:
    """Service for testing and validating patterns."""

    @staticmethod
    def extract_with_python_module(
        html: str,
        extractor_module: str
    ) -> Dict[str, Any]:
        """
        Extract data using a Python extractor module.

        Args:
            html: HTML content
            extractor_module: Module name (e.g., "generated_extractors.komplett_no")

        Returns:
            Dict with extracted field data
        """
        try:
            # Import generated_extractors
            from generated_extractors import get_parser, extract_from_html

            # Use the discovery API
            domain = extractor_module.replace('generated_extractors.', '')
            results = extract_from_html(domain, html)

            if not results:
                logger.warning(f"Python extractor {extractor_module} returned no results")
                return {}

            # Convert ExtractorResult to dict format compatible with existing code
            formatted_results = {}
            for field_name, value in results.items():
                if value is not None:
                    formatted_results[field_name] = {
                        'value': str(value),
                        'method': 'python_extractor',
                        'confidence': 1.0,  # Python extractors don't have confidence scores
                        'selector': extractor_module
                    }
                else:
                    formatted_results[field_name] = {
                        'value': None,
                        'error': 'Extractor returned None'
                    }

            return formatted_results

        except ImportError as e:
            logger.error(f"Failed to import Python extractor {extractor_module}: {e}")
            return {}
        except Exception as e:
            logger.exception(f"Python extractor {extractor_module} failed: {e}")
            return {}

    @staticmethod
    def test_pattern_against_url(
        url: str,
        extractor_module: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Test Python extractor against a URL.

        Args:
            url: URL to test against
            extractor_module: Python module name (e.g., "komplett_no")
            use_cache: Whether to use cached HTML

        Returns:
            Dict with test results and extraction data
        """
        try:
            # 1. Fetch HTML
            html, metadata = PatternTestService.fetch_html(url, use_cache=use_cache)

            # 2. Extract data using Python extractor
            extraction_result = PatternTestService.extract_with_python_module(html, extractor_module)

            # 3. Validate results
            validation = PatternTestService._validate_extraction(extraction_result)

            return {
                'success': extraction_result.get('price', {}).get('value') is not None,
                'extraction': extraction_result,
                'errors': validation['errors'],
                'warnings': validation['warnings'],
                'metadata': metadata
            }

        except Exception as e:
            logger.exception(f"Pattern test failed for {url}: {e}")
            return {
                'success': False,
                'extraction': {},
                'errors': [str(e)],
                'warnings': [],
                'metadata': {}
            }

    @staticmethod
    def fetch_html(url: str, use_cache: bool = True) -> Tuple[str, Dict]:
        """
        Fetch HTML from URL using stealth browser.

        Args:
            url: URL to fetch
            use_cache: Whether to use cached result

        Returns:
            Tuple of (html, metadata)
        """
        # Check cache first
        if use_cache:
            cache_key = f'pattern_test_html_{url}'
            cached = cache.get(cache_key)
            if cached:
                logger.info(f"Using cached HTML for {url}")
                return cached['html'], cached['metadata']

        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            raise ValueError('URL must use HTTP or HTTPS')

        # Fetch using Playwright browser automation (same as PriceFetcher)
        import asyncio
        from time import time
        from playwright.async_api import async_playwright

        async def fetch_with_browser(url: str) -> tuple:
            """Fetch HTML using Playwright browser."""
            start_time = time()

            async with async_playwright() as p:
                # Launch browser with stealth mode
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                    ]
                )

                # Create context with realistic options
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                )

                page = await context.new_page()

                # Navigate and wait for network idle (JavaScript rendering)
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Get rendered HTML
                html = await page.content()

                await browser.close()

                duration_ms = int((time() - start_time) * 1000)
                return html, duration_ms

        # Run async fetch in sync context
        html, duration_ms = asyncio.run(fetch_with_browser(url))

        metadata = {
            'fetch_time_ms': duration_ms,
            'html_size': len(html),
            'status_code': 200,
            'content_type': 'text/html',
        }

        # Cache for 5 minutes
        if use_cache:
            cache_key = f'pattern_test_html_{url}'
            cache.set(cache_key, {'html': html, 'metadata': metadata}, 300)

        return html, metadata

    @staticmethod
    def _validate_extraction(extraction: Dict) -> Dict[str, List[str]]:
        """Validate extraction results."""
        errors = []
        warnings = []

        # Check required fields
        if not extraction.get('price', {}).get('value'):
            errors.append('Price not found (required field)')

        if not extraction.get('title', {}).get('value'):
            warnings.append('Title not found')

        if not extraction.get('image', {}).get('value'):
            warnings.append('Image not found')

        return {'errors': errors, 'warnings': warnings}

    @staticmethod
    def test_pattern_for_visualization(pattern: Pattern) -> Dict[str, Any]:
        """
        Test Python extractor pattern for visualization page.

        Args:
            pattern: Pattern instance to test

        Returns:
            Dict with {success, test_url, extraction_results, metadata}
        """
        # Get test URL from most recent ProductListing
        test_url = ProductListing.objects.filter(
            store__domain=pattern.domain,
            active=True
        ).order_by('-last_checked').values_list('url', flat=True).first()

        if not test_url:
            return {
                'success': False,
                'error': 'No active product listings for this domain',
                'test_url': None,
                'extraction_results': {}
            }

        if not pattern.extractor_module:
            return {
                'success': False,
                'error': 'Pattern does not have a Python extractor module configured',
                'test_url': test_url,
                'extraction_results': {}
            }

        try:
            # Fetch HTML
            html, metadata = PatternTestService.fetch_html(test_url, use_cache=True)

            # Extract using Python module
            extraction_results = PatternTestService.extract_with_python_module(
                html,
                pattern.extractor_module
            )

            return {
                'success': bool(extraction_results),
                'test_url': test_url,
                'extraction_results': extraction_results,
                'metadata': metadata
            }

        except Exception as e:
            logger.exception(f"Error testing pattern for visualization: {e}")
            return {
                'success': False,
                'error': f'Test failed: {str(e)}',
                'test_url': test_url,
                'extraction_results': {}
            }
