"""Basic usage example for ExtractorPatternAgent."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import ExtractorPatternAgent


async def main():
    """Basic pattern generation example."""

    # Example product URL (replace with real URL)
    url = "https://www.example.com/product/sample-product"

    print(f"=== ExtractorPatternAgent - Basic Usage ===\n")
    print(f"Analyzing URL: {url}\n")

    # Initialize agent with context manager
    async with ExtractorPatternAgent() as agent:
        print("Agent initialized. Generating patterns...\n")

        # Generate extraction patterns
        patterns = await agent.generate_patterns(url, save_to_db=True)

        print("=== Generated Patterns ===")
        print(json.dumps(patterns, indent=2))
        print()

        # Display summary
        if "patterns" in patterns:
            print("=== Summary ===")
            pattern_data = patterns["patterns"]

            for field_name, field_pattern in pattern_data.items():
                primary = field_pattern.get("primary", {})
                confidence = primary.get("confidence", 0.0)
                selector_type = primary.get("type", "unknown")
                selector = primary.get("selector", "")

                print(f"  {field_name}:")
                print(f"    Type: {selector_type}")
                print(f"    Confidence: {confidence:.2f}")
                print(f"    Selector: {selector}")

                fallbacks = field_pattern.get("fallbacks", [])
                if fallbacks:
                    print(f"    Fallbacks: {len(fallbacks)}")
                print()

        # Save to file for reference
        output_file = Path(__file__).parent / "generated_patterns.json"
        with open(output_file, "w") as f:
            json.dump(patterns, f, indent=2)

        print(f"Patterns saved to: {output_file}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
