"""
Pattern Management Services.

Provides business logic for pattern management, testing, validation, and history tracking.
"""
import json
import subprocess
import logging
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from urllib.parse import urlparse

from django.utils import timezone
from django.db.models import Max, Q
from django.core.cache import cache

from .models import Pattern, PatternHistory, ProductListing, Store

logger = logging.getLogger(__name__)


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
        pattern_json: Dict,
        user,
        change_reason: str = 'Initial creation'
    ) -> Tuple[Pattern, bool]:
        """
        Create new pattern.

        Args:
            domain: Pattern domain
            pattern_json: Pattern JSON structure
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
                'pattern_json': pattern_json,
                'store': store,
                'last_validated': timezone.now()
            }
        )

        # Create initial history entry
        if created:
            PatternHistory.objects.create(
                pattern=pattern,
                domain=domain,
                version_number=1,
                pattern_json=pattern_json,
                changed_by=user,
                change_reason=change_reason,
                change_type='manual_edit',
                success_rate_at_time=0.0,
                total_attempts_at_time=0
            )

        return pattern, created

    @staticmethod
    def update_pattern(
        domain: str,
        pattern_json: Dict,
        user,
        change_reason: str = 'Manual edit'
    ) -> Pattern:
        """
        Update existing pattern.

        Args:
            domain: Pattern domain
            pattern_json: New pattern JSON
            user: User making the update
            change_reason: Reason for update

        Returns:
            Updated Pattern instance
        """
        pattern = Pattern.objects.get(domain=domain)

        # Save history before update (signal will handle this automatically)
        # But we want to set the user and reason, so we do it manually first
        last_version = PatternHistory.objects.filter(
            pattern=pattern
        ).aggregate(Max('version_number'))['version_number__max']

        next_version = (last_version or 0) + 1

        # Create history entry with current (old) data
        PatternHistory.objects.create(
            pattern=pattern,
            domain=pattern.domain,
            version_number=next_version,
            pattern_json=pattern.pattern_json,
            changed_by=user,
            change_reason=change_reason,
            change_type='manual_edit',
            success_rate_at_time=pattern.success_rate,
            total_attempts_at_time=pattern.total_attempts
        )

        # Update pattern
        pattern.pattern_json = pattern_json
        pattern.last_validated = timezone.now()
        pattern.save(update_fields=['pattern_json', 'last_validated', 'updated_at'])

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
    def test_pattern_against_url(
        url: str,
        pattern_json: Dict,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Comprehensive pattern testing against a URL.

        Args:
            url: URL to test against
            pattern_json: Pattern JSON to test
            use_cache: Whether to use cached HTML

        Returns:
            Dict with test results, extraction data, and selector details
        """
        try:
            # 1. Fetch HTML
            html, metadata = PatternTestService.fetch_html(url, use_cache=use_cache)

            # 2. Extract data using pattern
            extraction_result = PatternTestService.extract_with_pattern(html, pattern_json)

            # 3. Test each selector individually
            selector_results = PatternTestService._test_all_selectors(html, pattern_json)

            # 4. Validate results
            validation = PatternTestService._validate_extraction(extraction_result)

            return {
                'success': extraction_result.get('price', {}).get('value') is not None,
                'extraction': extraction_result,
                'selector_results': selector_results,
                'errors': validation['errors'],
                'warnings': validation['warnings'],
                'metadata': metadata
            }

        except Exception as e:
            logger.exception(f"Pattern test failed for {url}: {e}")
            return {
                'success': False,
                'extraction': {},
                'selector_results': [],
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
    def extract_with_pattern(html: str, pattern_json: Dict) -> Dict[str, Any]:
        """
        Extract data from HTML using pattern.

        Args:
            html: HTML content
            pattern_json: Pattern JSON

        Returns:
            Dict with extracted field data
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')
        results = {}

        patterns = pattern_json.get('patterns', {})

        for field_name, field_pattern in patterns.items():
            # Try primary selector first
            primary = field_pattern.get('primary', {})
            value = PatternTestService._extract_with_selector(soup, primary)

            if value:
                results[field_name] = {
                    'value': value,
                    'method': primary.get('type', 'unknown'),
                    'confidence': primary.get('confidence', 0.0),
                    'selector': primary.get('selector', '')
                }
            else:
                # Try fallbacks
                fallbacks = field_pattern.get('fallbacks', [])
                for i, fallback in enumerate(fallbacks):
                    value = PatternTestService._extract_with_selector(soup, fallback)
                    if value:
                        results[field_name] = {
                            'value': value,
                            'method': fallback.get('type', 'unknown'),
                            'confidence': fallback.get('confidence', 0.0),
                            'selector': fallback.get('selector', ''),
                            'fallback_index': i
                        }
                        break
                else:
                    results[field_name] = {
                        'value': None,
                        'error': 'No selector matched'
                    }

        return results

    @staticmethod
    def _extract_with_selector(soup, selector_config: Dict) -> Optional[str]:
        """Extract value using a single selector."""
        try:
            selector_type = selector_config.get('type')
            selector = selector_config.get('selector')
            attribute = selector_config.get('attribute')

            if selector_type == 'css':
                element = soup.select_one(selector)
                if element:
                    if attribute:
                        return element.get(attribute)
                    return element.get_text(strip=True)

            elif selector_type == 'xpath':
                # BeautifulSoup doesn't support XPath, would need lxml
                from lxml import html as lxml_html
                tree = lxml_html.fromstring(str(soup))
                elements = tree.xpath(selector)
                if elements:
                    if attribute:
                        return elements[0].get(attribute)
                    return elements[0].text_content().strip()

            elif selector_type == 'meta':
                element = soup.find('meta', attrs={'property': selector})
                if element:
                    return element.get('content')

            return None

        except Exception as e:
            logger.debug(f"Selector extraction failed: {e}")
            return None

    @staticmethod
    def _test_all_selectors(html: str, pattern_json: Dict) -> List[Dict]:
        """Test each selector (primary + fallbacks) individually."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')
        results = []

        patterns = pattern_json.get('patterns', {})

        for field_name, field_pattern in patterns.items():
            # Test primary
            primary = field_pattern.get('primary', {})
            value = PatternTestService._extract_with_selector(soup, primary)

            results.append({
                'field': field_name,
                'type': 'primary',
                'selector': primary.get('selector', ''),
                'selector_type': primary.get('type', ''),
                'matched': value is not None,
                'value': value[:100] if value else None,  # Truncate long values
                'confidence': primary.get('confidence', 0.0)
            })

            # Test fallbacks
            fallbacks = field_pattern.get('fallbacks', [])
            for i, fallback in enumerate(fallbacks):
                value = PatternTestService._extract_with_selector(soup, fallback)

                results.append({
                    'field': field_name,
                    'type': f'fallback_{i+1}',
                    'selector': fallback.get('selector', ''),
                    'selector_type': fallback.get('type', ''),
                    'matched': value is not None,
                    'value': value[:100] if value else None,
                    'confidence': fallback.get('confidence', 0.0)
                })

        return results

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
    def validate_pattern_syntax(pattern_json: Dict) -> Dict[str, Any]:
        """
        Validate pattern JSON structure and syntax.

        Args:
            pattern_json: Pattern JSON to validate

        Returns:
            Dict with validation result
        """
        from . import pattern_validators

        errors = []
        warnings = []

        # Validate structure
        structure_result = pattern_validators.validate_pattern_structure(pattern_json)
        if not structure_result['valid']:
            errors.extend(structure_result['errors'])

        # Validate each selector syntax
        patterns = pattern_json.get('patterns', {})
        for field_name, field_pattern in patterns.items():
            # Validate primary
            primary = field_pattern.get('primary', {})
            selector_type = primary.get('type')
            selector = primary.get('selector')

            if selector_type and selector:
                is_valid = pattern_validators.validate_selector_syntax(selector_type, selector)
                if not is_valid:
                    errors.append(f'{field_name}.primary: Invalid {selector_type} selector syntax')

            # Validate fallbacks
            for i, fallback in enumerate(field_pattern.get('fallbacks', [])):
                selector_type = fallback.get('type')
                selector = fallback.get('selector')

                if selector_type and selector:
                    is_valid = pattern_validators.validate_selector_syntax(selector_type, selector)
                    if not is_valid:
                        errors.append(
                            f'{field_name}.fallbacks[{i}]: Invalid {selector_type} selector syntax'
                        )

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @staticmethod
    def test_single_selector(
        html: str,
        selector_config: Dict
    ) -> Dict[str, Any]:
        """
        Test a single selector against HTML.

        Args:
            html: HTML content
            selector_config: Selector configuration

        Returns:
            Dict with test result
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')

        try:
            value = PatternTestService._extract_with_selector(soup, selector_config)

            return {
                'matched': value is not None,
                'value': value,
                'error': None
            }

        except Exception as e:
            return {
                'matched': False,
                'value': None,
                'error': str(e)
            }

    @staticmethod
    def _extract_with_html_capture(html: str, selector_config: Dict) -> Dict:
        """
        Extract value and capture HTML snippet.

        Args:
            html: HTML content
            selector_config: Selector configuration dict

        Returns:
            Dict with {matched, value, html_snippet, match_count}
        """
        from bs4 import BeautifulSoup
        from lxml import html as lxml_html
        import json as json_module

        selector_type = selector_config.get('type')
        selector = selector_config.get('selector')
        attribute = selector_config.get('attribute')

        try:
            if selector_type == 'css':
                soup = BeautifulSoup(html, 'html.parser')
                elements = soup.select(selector)  # Get ALL matches

                if not elements:
                    return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

                element = elements[0]  # Use first match
                value = element.get(attribute) if attribute else element.get_text(strip=True)
                html_snippet = str(element)[:500]  # Truncate to 500 chars

                return {
                    'matched': True,
                    'value': value,
                    'html_snippet': html_snippet,
                    'match_count': len(elements)
                }

            elif selector_type == 'xpath':
                tree = lxml_html.fromstring(html)
                elements = tree.xpath(selector)

                if not elements:
                    return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

                element = elements[0]
                value = element.get(attribute) if attribute and hasattr(element, 'get') else (
                    element.text_content().strip() if hasattr(element, 'text_content') else str(element)
                )
                html_snippet = lxml_html.tostring(element, encoding='unicode')[:500]

                return {
                    'matched': True,
                    'value': value,
                    'html_snippet': html_snippet,
                    'match_count': len(elements)
                }

            elif selector_type == 'meta':
                soup = BeautifulSoup(html, 'html.parser')
                element = soup.find('meta', attrs={'property': selector})

                if not element:
                    return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

                value = element.get('content')
                html_snippet = str(element)

                return {'matched': True, 'value': value, 'html_snippet': html_snippet, 'match_count': 1}

            elif selector_type == 'jsonld' or selector_type == 'json_ld':
                # Use existing JSON-LD extraction logic
                soup = BeautifulSoup(html, 'html.parser')
                scripts = soup.find_all('script', type='application/ld+json')

                json_path = selector_config.get('json_path', '')

                for script in scripts:
                    try:
                        data = json_module.loads(script.string)
                        # Navigate JSON path
                        value = data
                        for key in json_path.split('.'):
                            if not key:  # Skip empty keys
                                continue
                            if key.isdigit():
                                value = value[int(key)]
                            else:
                                value = value.get(key) if isinstance(value, dict) else None
                            if value is None:
                                break

                        if value:
                            return {
                                'matched': True,
                                'value': str(value),
                                'html_snippet': f'<script type="application/ld+json">...{json_path}: {value}...</script>',
                                'match_count': 1
                            }
                    except:
                        continue

                return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

            return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

        except Exception as e:
            logger.exception(f"Error extracting with HTML capture: {e}")
            return {'matched': False, 'value': None, 'html_snippet': None, 'match_count': 0}

    @staticmethod
    def test_pattern_for_visualization(pattern: Pattern) -> Dict[str, Any]:
        """
        Test pattern for visualization page with enhanced selector details.

        Args:
            pattern: Pattern instance to test

        Returns:
            Dict with {success, test_url, fields[], metadata}
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
                'fields': []
            }

        try:
            # Fetch HTML
            html, metadata = PatternTestService.fetch_html(test_url, use_cache=True)

            # Test each field's selectors
            fields_data = []
            for field_name, field_pattern in pattern.pattern_json.get('patterns', {}).items():
                field_data = {'name': field_name, 'selectors': []}

                # Test primary selector
                primary = field_pattern.get('primary', {})
                if primary:
                    primary_result = PatternTestService._extract_with_html_capture(html, primary)
                    field_data['selectors'].append({
                        'type': 'primary',
                        'selector_type': primary.get('type'),
                        'selector': primary.get('selector'),
                        'matched': primary_result['matched'],
                        'match_count': primary_result['match_count'],
                        'extracted_value': primary_result['value'],
                        'html_snippet': primary_result['html_snippet'],
                        'confidence': primary.get('confidence', 0.0)
                    })

                # Test fallback selectors
                for i, fallback in enumerate(field_pattern.get('fallbacks', [])):
                    fallback_result = PatternTestService._extract_with_html_capture(html, fallback)
                    field_data['selectors'].append({
                        'type': f'fallback_{i+1}',
                        'selector_type': fallback.get('type'),
                        'selector': fallback.get('selector'),
                        'matched': fallback_result['matched'],
                        'match_count': fallback_result['match_count'],
                        'extracted_value': fallback_result['value'],
                        'html_snippet': fallback_result['html_snippet'],
                        'confidence': fallback.get('confidence', 0.0)
                    })

                fields_data.append(field_data)

            return {
                'success': True,
                'test_url': test_url,
                'fields': fields_data,
                'metadata': metadata
            }

        except Exception as e:
            logger.exception(f"Error testing pattern for visualization: {e}")
            return {
                'success': False,
                'error': f'Test failed: {str(e)}',
                'test_url': test_url,
                'fields': []
            }
