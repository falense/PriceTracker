#!/usr/bin/env python3
"""
Test extractor patterns against saved HTML samples.

Usage:
    python scripts/test_extractor.py oda.com
    python scripts/test_extractor.py oda.com --sample sample_20251220_232515
    python scripts/test_extractor.py oda.com --all-samples
"""

import sys
import argparse
import importlib
from pathlib import Path
from typing import Optional, Dict, Any
from decimal import Decimal
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    

def load_extractor_module(domain: str):
    """
    Load the extractor module for a domain.
    
    Args:
        domain: Domain name (e.g., "oda.com")
        
    Returns:
        Loaded module or None if not found
    """
    # Convert domain to module name (replace dots with underscores)
    module_name = domain.replace('.', '_').replace('-', '_')
    
    # Use importlib to import from generated_extractors package
    try:
        # Import the package-relative module
        from generated_extractors import _base  # Ensure _base is available
        module = importlib.import_module(f'generated_extractors.{module_name}')
        return module
    except ImportError as e:
        print(f"Error: Could not import extractor module for {domain}: {e}")
        return None
    except Exception as e:
        print(f"Error loading extractor: {e}")
        return None


def find_samples(domain: str, sample_name: Optional[str] = None) -> list[Path]:
    """
    Find sample directories for a domain.
    
    Args:
        domain: Domain name
        sample_name: Specific sample name or None for latest
        
    Returns:
        List of sample directory paths
    """
    test_data_dir = Path(__file__).parent.parent / 'test_data'
    domain_dir = test_data_dir / domain.replace('.', '_').replace('-', '_')
    
    if not domain_dir.exists():
        print(f"Error: No test data found for {domain} at {domain_dir}")
        return []
    
    if sample_name:
        # Specific sample requested
        sample_dir = domain_dir / sample_name
        if sample_dir.exists():
            return [sample_dir]
        else:
            print(f"Error: Sample {sample_name} not found in {domain_dir}")
            return []
    
    # Get all samples sorted by timestamp (newest first)
    samples = sorted(
        [d for d in domain_dir.iterdir() if d.is_dir() and d.name.startswith('sample_')],
        reverse=True
    )
    
    if not samples:
        print(f"Error: No samples found in {domain_dir}")
        return []
    
    return samples


def test_extractor(module, sample_dir: Path) -> Dict[str, Any]:
    """
    Test an extractor against a sample.
    
    Args:
        module: Loaded extractor module
        sample_dir: Path to sample directory
        
    Returns:
        Dictionary with test results
    """
    html_path = sample_dir / 'page.html'
    
    if not html_path.exists():
        return {
            'error': f"HTML file not found: {html_path}",
            'sample_dir': sample_dir.name
        }
    
    # Load HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'lxml')
    
    # Extract all fields
    results = {
        'sample_dir': sample_dir.name,
        'fields': {}
    }
    
    # Test each extraction function
    fields = ['price', 'title', 'image', 'availability', 'article_number', 'model_number']
    
    for field in fields:
        func_name = f'extract_{field}'
        if hasattr(module, func_name):
            try:
                func = getattr(module, func_name)
                value = func(soup)
                results['fields'][field] = {
                    'success': value is not None,
                    'value': value
                }
            except Exception as e:
                results['fields'][field] = {
                    'success': False,
                    'error': str(e)
                }
        else:
            results['fields'][field] = {
                'success': False,
                'error': f'Function {func_name} not found'
            }
    
    return results


def print_results(results: Dict[str, Any], metadata: Optional[Dict] = None):
    """Print test results in a formatted table."""
    sample_name = results.get('sample_dir', 'Unknown')
    
    if 'error' in results:
        print(f"Error testing {sample_name}: {results['error']}")
        return
    
    if RICH_AVAILABLE:
        console = Console()
        
        # Print header
        console.print(f"\n[bold]Testing Sample:[/bold] {sample_name}")
        if metadata:
            domain = metadata.get('domain', 'Unknown')
            console.print(f"[bold]Domain:[/bold] {domain}")
        
        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Field", style="dim", width=20)
        table.add_column("Status", width=12)
        table.add_column("Extracted Value", width=60)
        
        fields_data = results.get('fields', {})
        success_count = 0
        total_count = len(fields_data)
        
        # Required fields for critical check
        required_fields = ['price', 'title']
        critical_success = True
        
        for field, data in fields_data.items():
            success = data.get('success', False)
            if success:
                success_count += 1
            
            # Check critical fields
            if field in required_fields and not success:
                critical_success = False
            
            status = "✓ PASS" if success else "✗ FAIL"
            status_color = "green" if success else "red"
            
            value = data.get('value')
            if value is None:
                display_value = "-"
            elif isinstance(value, Decimal):
                display_value = str(value)
            elif isinstance(value, str):
                # Truncate long strings
                display_value = value[:60] + "..." if len(value) > 60 else value
            else:
                display_value = str(value)
            
            # Show error if present
            if 'error' in data:
                display_value = f"Error: {data['error'][:40]}"
            
            table.add_row(
                field,
                f"[{status_color}]{status}[/{status_color}]",
                display_value
            )
        
        console.print(table)
        
        # Print summary
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        console.print(f"\n[bold]Summary:[/bold] {success_count}/{total_count} fields extracted ({success_rate:.1f}%)")
        
        # Critical fields check
        if critical_success:
            console.print("[green]✓ Critical fields: Price, Title[/green]")
        else:
            console.print("[red]✗ Missing critical fields (Price and/or Title)[/red]")
    else:
        # Fallback to plain text
        print(f"\nTesting Sample: {sample_name}")
        if metadata:
            print(f"Domain: {metadata.get('domain', 'Unknown')}")
        
        print("\nResults:")
        print("-" * 80)
        
        fields_data = results.get('fields', {})
        success_count = 0
        total_count = len(fields_data)
        
        for field, data in fields_data.items():
            success = data.get('success', False)
            if success:
                success_count += 1
            
            status = "PASS" if success else "FAIL"
            value = data.get('value', '-')
            
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            
            print(f"{field:20s} [{status:4s}]  {value}")
        
        print("-" * 80)
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        print(f"Summary: {success_count}/{total_count} fields extracted ({success_rate:.1f}%)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test extractor patterns against saved HTML samples'
    )
    parser.add_argument(
        'domain',
        help='Domain to test (e.g., oda.com, komplett.no)'
    )
    parser.add_argument(
        '--sample',
        help='Specific sample directory name to test'
    )
    parser.add_argument(
        '--all-samples',
        action='store_true',
        help='Test against all available samples'
    )
    
    args = parser.parse_args()
    
    # Load the extractor module
    print(f"Loading extractor for {args.domain}...")
    module = load_extractor_module(args.domain)
    if not module:
        return 1
    
    # Get metadata if available
    metadata = getattr(module, 'PATTERN_METADATA', None)
    if metadata:
        print(f"Pattern version: {metadata.get('version', 'Unknown')}")
        print(f"Confidence: {metadata.get('confidence', 'Unknown')}")
    
    # Find samples
    if args.all_samples:
        samples = find_samples(args.domain)
        if not samples:
            return 1
        print(f"Found {len(samples)} sample(s)")
    else:
        samples = find_samples(args.domain, args.sample)
        if not samples:
            return 1
        if not args.sample:
            print(f"Testing against latest sample: {samples[0].name}")
    
    # Test each sample
    for sample_dir in samples:
        results = test_extractor(module, sample_dir)
        print_results(results, metadata)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
