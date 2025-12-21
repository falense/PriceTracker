#!/usr/bin/env python3
"""
Test Python extractor against HTML samples.

Usage:
    python scripts/test_extractor.py komplett.no
    python scripts/test_extractor.py komplett.no --all-samples
    python scripts/test_extractor.py komplett.no --json
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
# We need PriceTracker in path so ExtractorPatternAgent can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ExtractorPatternAgent.generated_extractors import extract_from_html, has_parser
from rich.console import Console
from rich.table import Table


class ExtractorTester:
    """Test extractors against HTML samples."""

    def __init__(self):
        """Initialize ExtractorTester."""
        self.base_dir = Path(__file__).parent.parent
        self.console = Console()

    def test_extractor(
        self,
        domain: str,
        sample_name: str = None,
        output_format: str = "table"
    ) -> Dict:
        """
        Test extractor against a sample.

        Args:
            domain: Domain to test
            sample_name: Specific sample directory name (default: latest)
            output_format: Output format ('table' or 'json')

        Returns:
            Test results dict

        Raises:
            FileNotFoundError: If domain has no samples or extractor doesn't exist
        """
        # Find sample
        sample_path = self._find_sample(domain, sample_name)

        # Load HTML
        html_file = sample_path / "page.html"
        if not html_file.exists():
            raise FileNotFoundError(f"No HTML file found in sample: {sample_path}")

        html = html_file.read_text(encoding='utf-8')

        # Load metadata
        metadata_file = sample_path / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text())

        # Check if extractor exists
        if not has_parser(domain):
            raise FileNotFoundError(
                f"No extractor found for domain: {domain}\n"
                f"Create extractor at: generated_extractors/{domain.replace('.', '_')}.py"
            )

        # Run extraction
        result = extract_from_html(domain, html)

        # Build test results
        test_results = self._build_results(result, metadata, sample_path.name)

        # Display results
        if output_format == "table":
            self._display_table(domain, sample_path.name, test_results)
        elif output_format == "json":
            self._display_json(domain, sample_path.name, test_results)
        else:
            self._display_simple(domain, sample_path.name, test_results)

        return test_results

    def test_all_samples(
        self,
        domain: str,
        output_format: str = "simple"
    ) -> List[Dict]:
        """
        Test extractor against all samples for a domain.

        Args:
            domain: Domain to test
            output_format: Output format ('table', 'json', or 'simple')

        Returns:
            List of test results for each sample
        """
        test_data_dir = self.base_dir / "test_data" / domain.replace('.', '_')

        if not test_data_dir.exists():
            self.console.print(f"[red]No samples found for {domain}[/red]")
            return []

        samples = sorted(test_data_dir.glob("sample_*"), reverse=True)

        if not samples:
            self.console.print(f"[red]No samples found for {domain}[/red]")
            return []

        all_results = []
        for i, sample_path in enumerate(samples):
            if i > 0:  # Add separator between samples
                self.console.print()

            self.console.print(f"[bold]Testing: {sample_path.name}[/bold]")

            try:
                results = self.test_extractor(
                    domain,
                    sample_name=sample_path.name,
                    output_format=output_format
                )
                all_results.append(results)
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                continue

        # Summary
        if all_results:
            self._display_aggregate_summary(all_results)

        return all_results

    def _find_sample(self, domain: str, sample_name: str = None) -> Path:
        """
        Find sample directory for domain.

        Args:
            domain: Domain name
            sample_name: Specific sample directory name (optional)

        Returns:
            Path to sample directory

        Raises:
            FileNotFoundError: If no samples found
        """
        test_data_dir = self.base_dir / "test_data" / domain.replace('.', '_')

        if not test_data_dir.exists():
            raise FileNotFoundError(
                f"No samples found for {domain}\n"
                f"Run: python scripts/fetch_sample.py <url>"
            )

        if sample_name:
            sample_path = test_data_dir / sample_name
            if not sample_path.exists():
                raise FileNotFoundError(f"Sample not found: {sample_name}")
            return sample_path

        # Find latest sample
        samples = sorted(test_data_dir.glob("sample_*"), reverse=True)
        if not samples:
            raise FileNotFoundError(
                f"No samples found for {domain}\n"
                f"Run: python scripts/fetch_sample.py <url>"
            )

        return samples[0]

    def _build_results(self, extraction_result, metadata: Dict, sample_name: str) -> Dict:
        """
        Build test results from extraction.

        Args:
            extraction_result: ExtractorResult from extract_from_html()
            metadata: Sample metadata
            sample_name: Sample directory name

        Returns:
            Dict with test results
        """
        fields = ["price", "title", "image", "availability", "article_number", "model_number"]

        results = {}
        for field in fields:
            extracted = getattr(extraction_result, field, None)

            # Determine status: PASS if extracted (not None), FAIL if None
            status = "pass" if extracted is not None else "fail"

            results[field] = {
                "extracted": str(extracted) if extracted is not None else None,
                "status": status
            }

        # Calculate summary
        total_fields = len(fields)
        extracted_count = sum(1 for r in results.values() if r["status"] == "pass")
        success_rate = extracted_count / total_fields if total_fields > 0 else 0.0

        # Check critical fields (price and title)
        critical_fields_ok = (
            results["price"]["status"] == "pass" and
            results["title"]["status"] == "pass"
        )

        return {
            "sample": sample_name,
            "metadata": metadata,
            "results": results,
            "summary": {
                "total_fields": total_fields,
                "extracted": extracted_count,
                "success_rate": success_rate,
                "critical_fields_ok": critical_fields_ok
            }
        }

    def _display_table(self, domain: str, sample_name: str, test_results: Dict):
        """
        Display results as rich table.

        Args:
            domain: Domain name
            sample_name: Sample directory name
            test_results: Test results dict
        """
        self.console.print(f"\n[bold]Testing:[/bold] {domain}")
        self.console.print(f"[bold]Sample:[/bold] {sample_name}")

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Field", style="cyan", width=16)
        table.add_column("Status", width=9)
        table.add_column("Extracted Value", max_width=50)

        results = test_results["results"]
        for field, data in results.items():
            status_icon = "✓" if data["status"] == "pass" else "✗"
            status_color = "green" if data["status"] == "pass" else "red"

            extracted_val = data["extracted"] if data["extracted"] else "-"

            table.add_row(
                field,
                f"[{status_color}]{status_icon} {data['status'].upper()}[/{status_color}]",
                extracted_val
            )

        self.console.print(table)

        # Summary
        summary = test_results["summary"]
        success_rate_pct = summary["success_rate"] * 100

        self.console.print(
            f"\n[bold]Summary:[/bold] {summary['extracted']}/{summary['total_fields']} "
            f"fields extracted ({success_rate_pct:.1f}%)"
        )

        if summary["critical_fields_ok"]:
            self.console.print("[green]Critical fields: ✓ Price, ✓ Title[/green]")
        else:
            self.console.print("[red]Critical fields: FAILED (Price or Title missing)[/red]")

    def _display_json(self, domain: str, sample_name: str, test_results: Dict):
        """
        Display results as JSON.

        Args:
            domain: Domain name
            sample_name: Sample directory name
            test_results: Test results dict
        """
        output = {
            "domain": domain,
            "sample": sample_name,
            "results": test_results["results"],
            "summary": test_results["summary"]
        }
        print(json.dumps(output, indent=2))

    def _display_simple(self, domain: str, sample_name: str, test_results: Dict):
        """
        Display results in simple text format.

        Args:
            domain: Domain name
            sample_name: Sample directory name
            test_results: Test results dict
        """
        print(f"\nTesting: {domain}")
        print(f"Sample: {sample_name}")
        print()

        results = test_results["results"]
        for field, data in results.items():
            status_icon = "✓" if data["status"] == "pass" else "✗"
            extracted_val = data["extracted"] if data["extracted"] else "None"
            print(f"{status_icon} {field:15} {extracted_val}")

        summary = test_results["summary"]
        success_rate_pct = summary["success_rate"] * 100
        print(f"\nSummary: {summary['extracted']}/{summary['total_fields']} fields ({success_rate_pct:.1f}%)")

    def _display_aggregate_summary(self, all_results: List[Dict]):
        """
        Display aggregate summary for multiple samples.

        Args:
            all_results: List of test result dicts
        """
        if not all_results:
            return

        self.console.print("\n[bold]═══ Aggregate Summary ═══[/bold]")

        total_samples = len(all_results)
        total_success = sum(1 for r in all_results if r["summary"]["critical_fields_ok"])

        # Average success rate across all fields
        avg_success_rate = sum(r["summary"]["success_rate"] for r in all_results) / total_samples
        avg_success_rate_pct = avg_success_rate * 100

        self.console.print(f"Samples tested: {total_samples}")
        self.console.print(f"Critical fields passed: {total_success}/{total_samples}")
        self.console.print(f"Average extraction rate: {avg_success_rate_pct:.1f}%")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Test Python extractor against HTML samples',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s komplett.no
  %(prog)s komplett.no --sample sample_20250117_143022
  %(prog)s komplett.no --all-samples
  %(prog)s komplett.no --json
        '''
    )

    parser.add_argument(
        'domain',
        help='Domain to test (e.g., komplett.no, amazon.com)'
    )

    parser.add_argument(
        '--sample',
        help='Specific sample directory name (default: latest)'
    )

    parser.add_argument(
        '--all-samples',
        action='store_true',
        help='Test against all samples for the domain'
    )

    parser.add_argument(
        '--format',
        choices=['table', 'json', 'simple'],
        default='table',
        help='Output format (default: table)'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON (shortcut for --format json)'
    )

    args = parser.parse_args()

    # Handle --json flag
    output_format = 'json' if args.json else args.format

    try:
        tester = ExtractorTester()

        if args.all_samples:
            tester.test_all_samples(args.domain, output_format='simple')
        else:
            tester.test_extractor(args.domain, args.sample, output_format)

        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
