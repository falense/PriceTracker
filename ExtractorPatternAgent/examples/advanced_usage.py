"""Advanced usage example with validation loop and refinement."""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import ExtractorPatternAgent


async def generate_with_validation(url: str, max_retries: int = 3, min_confidence: float = 0.7) -> Dict[str, Any]:
    """
    Generate patterns with validation loop and automatic refinement.

    Args:
        url: Product page URL
        max_retries: Maximum number of generation attempts
        min_confidence: Minimum required confidence score

    Returns:
        Validated extraction patterns
    """
    print(f"=== Pattern Generation with Validation ===\n")
    print(f"URL: {url}")
    print(f"Max retries: {max_retries}")
    print(f"Min confidence: {min_confidence}\n")

    async with ExtractorPatternAgent() as agent:
        for attempt in range(1, max_retries + 1):
            print(f"--- Attempt {attempt}/{max_retries} ---\n")

            # Generate patterns
            print("Generating patterns...")
            patterns = await agent.generate_patterns(url, save_to_db=False)

            # Check if generation was successful
            if not patterns.get("patterns"):
                print("❌ Pattern generation failed - no patterns returned")
                if attempt < max_retries:
                    print("Retrying...\n")
                    continue
                else:
                    raise Exception("Failed to generate patterns after all retries")

            # Display generated patterns
            print("\n✓ Patterns generated")
            print(f"Fields: {', '.join(patterns['patterns'].keys())}\n")

            # Validate patterns
            print("Validating patterns...")
            validation = await agent.validate_patterns(url, patterns)

            # Check validation results
            if isinstance(validation, dict):
                success = validation.get("success", False)
                confidence = validation.get("overall_confidence", 0.0)

                print(f"\nValidation result: {'✓ PASSED' if success else '✗ FAILED'}")
                print(f"Overall confidence: {confidence:.2f}\n")

                # Display field-level results
                field_validations = validation.get("field_validations", {})
                if field_validations:
                    print("Field-level results:")
                    for field_name, field_result in field_validations.items():
                        field_success = field_result.get("valid", False)
                        field_confidence = field_result.get("confidence", 0.0)
                        status = "✓" if field_success else "✗"
                        print(f"  {status} {field_name}: confidence={field_confidence:.2f}")
                    print()

                # Check if patterns meet requirements
                if success and confidence >= min_confidence:
                    print(f"✓ Patterns validated successfully with confidence {confidence:.2f}")

                    # Save to database
                    print("Saving patterns to database...")
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc

                    save_result = await agent.query(
                        f"Save these patterns for domain '{domain}' with confidence {confidence}: {json.dumps(patterns)}"
                    )

                    print("✓ Patterns saved successfully\n")

                    return {
                        "success": True,
                        "patterns": patterns,
                        "validation": validation,
                        "attempts": attempt
                    }
                else:
                    # Identify errors for refinement
                    errors = validation.get("errors", [])
                    failed_fields = [
                        f for f, v in field_validations.items() if not v.get("valid", False)
                    ]

                    print(f"✗ Validation failed (confidence {confidence:.2f} < {min_confidence})")
                    if failed_fields:
                        print(f"Failed fields: {', '.join(failed_fields)}")
                    if errors:
                        print(f"Errors: {', '.join(errors)}")
                    print()

                    if attempt < max_retries:
                        # Refine patterns based on feedback
                        print("Refining patterns based on feedback...\n")

                        feedback = f"""
Validation failed with confidence {confidence:.2f} (target: {min_confidence}).

Failed fields: {', '.join(failed_fields) if failed_fields else 'None'}
Errors: {', '.join(errors) if errors else 'None'}

Please generate more robust selectors for the failed fields.
"""
                        patterns = await agent.refine_patterns(feedback)
                    else:
                        print(f"❌ Maximum retries ({max_retries}) reached")
                        return {
                            "success": False,
                            "patterns": patterns,
                            "validation": validation,
                            "attempts": attempt
                        }

        raise Exception("Failed to generate valid patterns")


async def test_multiple_urls():
    """Test pattern generation and validation across multiple URLs."""
    urls = [
        "https://www.example.com/product/sample-1",
        "https://www.example.com/product/sample-2",
        # Add more test URLs
    ]

    print("=== Multi-URL Pattern Testing ===\n")

    results = []

    for i, url in enumerate(urls, 1):
        print(f"\n{'='*60}")
        print(f"Testing URL {i}/{len(urls)}")
        print(f"{'='*60}\n")

        try:
            result = await generate_with_validation(url, max_retries=2, min_confidence=0.75)
            results.append({
                "url": url,
                "success": result["success"],
                "attempts": result["attempts"],
                "confidence": result.get("validation", {}).get("overall_confidence", 0.0)
            })
        except Exception as e:
            print(f"❌ Error processing URL: {e}\n")
            results.append({
                "url": url,
                "success": False,
                "error": str(e)
            })

    # Summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}\n")

    successful = sum(1 for r in results if r["success"])
    print(f"Total URLs tested: {len(urls)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(urls) - successful}")
    print()

    for result in results:
        status = "✓" if result["success"] else "✗"
        url = result["url"]
        if result["success"]:
            confidence = result.get("confidence", 0.0)
            attempts = result.get("attempts", 0)
            print(f"{status} {url} (confidence: {confidence:.2f}, attempts: {attempts})")
        else:
            error = result.get("error", "Unknown error")
            print(f"{status} {url} - {error}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Advanced ExtractorPatternAgent usage")
    parser.add_argument("url", nargs="?", help="Product URL to analyze")
    parser.add_argument("--multi-test", action="store_true", help="Run multi-URL test")
    parser.add_argument("--retries", type=int, default=3, help="Max retry attempts")
    parser.add_argument("--min-confidence", type=float, default=0.7, help="Minimum confidence")

    args = parser.parse_args()

    if args.multi_test:
        await test_multiple_urls()
    elif args.url:
        result = await generate_with_validation(
            args.url,
            max_retries=args.retries,
            min_confidence=args.min_confidence
        )

        # Save result
        output_file = Path(__file__).parent / "validation_result.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\nResult saved to: {output_file}")
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
