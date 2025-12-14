#!/usr/bin/env python3
"""
Test script to verify storage integration with Django database.

This test ensures that the ExtractorPatternAgent can properly save and
retrieve patterns from the shared Django database.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import storage module directly to avoid importing all tools
import importlib.util
spec = importlib.util.spec_from_file_location(
    "storage",
    Path(__file__).parent.parent / "src" / "tools" / "storage.py"
)
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)

# Get the actual function implementations (not the tool wrappers)
# The @tool decorator wraps functions, so we access the original implementation
def get_tool_func(tool_obj):
    """Extract the original function from a tool wrapper."""
    if hasattr(tool_obj, 'func'):
        return tool_obj.func
    elif hasattr(tool_obj, '__wrapped__'):
        return tool_obj.__wrapped__
    return tool_obj

save_pattern_tool = get_tool_func(storage.save_pattern_tool)
load_pattern_tool = get_tool_func(storage.load_pattern_tool)
list_patterns_tool = get_tool_func(storage.list_patterns_tool)
delete_pattern_tool = get_tool_func(storage.delete_pattern_tool)
update_pattern_stats_tool = get_tool_func(storage.update_pattern_stats_tool)
DJANGO_AVAILABLE = storage.DJANGO_AVAILABLE


async def test_storage_integration():
    """Run comprehensive storage integration tests."""

    print("="*60)
    print("ExtractorPatternAgent Storage Integration Test")
    print("="*60)
    print()

    # Check Django availability
    if not DJANGO_AVAILABLE:
        print("❌ FAILED: Django ORM not available")
        print("   Make sure Django database is set up correctly")
        return False

    print("✓ Django ORM is available\n")

    # Test domain
    test_domain = "test-storage.example.com"

    # Test patterns
    test_patterns = {
        "price": {
            "primary": {
                "type": "css",
                "selector": ".product-price",
                "confidence": 0.95
            },
            "fallbacks": [
                {
                    "type": "xpath",
                    "selector": "//span[@class='price']",
                    "confidence": 0.85
                }
            ]
        },
        "title": {
            "primary": {
                "type": "css",
                "selector": "#product-title",
                "confidence": 0.90
            }
        },
        "availability": {
            "primary": {
                "type": "jsonld",
                "selector": "offers.availability",
                "confidence": 0.98
            }
        }
    }

    test_confidence = 0.92

    # Test 1: Save pattern
    print("Test 1: Save Pattern")
    print("-" * 40)

    result = await save_pattern_tool({
        "domain": test_domain,
        "patterns": test_patterns,
        "confidence": test_confidence
    })

    print(f"Result: {result['content'][0]['text']}")

    data = json.loads(result['content'][0]['text'])
    if data.get("success"):
        print("✓ Pattern saved successfully\n")
    else:
        print(f"❌ Failed to save pattern: {data.get('error')}\n")
        return False

    # Test 2: Load pattern
    print("Test 2: Load Pattern")
    print("-" * 40)

    result = await load_pattern_tool({
        "domain": test_domain
    })

    data = json.loads(result['content'][0]['text'])

    if data.get("success"):
        print(f"✓ Pattern loaded successfully")
        print(f"  Domain: {data['domain']}")
        print(f"  Confidence: {data['confidence']}")
        print(f"  Success Rate: {data['success_rate']}")
        print(f"  Total Attempts: {data['total_attempts']}")

        # Verify patterns match
        loaded_patterns = data.get("patterns", {})
        if "price" in loaded_patterns and "title" in loaded_patterns:
            print("✓ Pattern data matches expected structure\n")
        else:
            print("❌ Pattern data structure incorrect\n")
            return False
    else:
        print(f"❌ Failed to load pattern: {data.get('error', 'Unknown error')}\n")
        return False

    # Test 3: Update pattern stats
    print("Test 3: Update Pattern Stats")
    print("-" * 40)

    # Simulate successful extraction
    result = await update_pattern_stats_tool({
        "domain": test_domain,
        "success": True
    })

    data = json.loads(result['content'][0]['text'])

    if data.get("success"):
        print(f"✓ Stats updated successfully")
        print(f"  Success Rate: {data['success_rate']:.1%}")
        print(f"  Total Attempts: {data['total_attempts']}")
        print(f"  Successful Attempts: {data['successful_attempts']}")
        print(f"  Is Healthy: {data['is_healthy']}\n")
    else:
        print(f"❌ Failed to update stats: {data.get('error', 'Unknown error')}\n")
        return False

    # Test 4: List patterns
    print("Test 4: List Patterns")
    print("-" * 40)

    result = await list_patterns_tool({})

    data = json.loads(result['content'][0]['text'])

    if data.get("success"):
        print(f"✓ Listed {data['count']} pattern(s)")

        # Check if our test pattern is in the list
        found_test = False
        for pattern in data.get("patterns", []):
            if pattern["domain"] == test_domain:
                found_test = True
                print(f"  Found test pattern: {test_domain}")
                print(f"    Confidence: {pattern['confidence']}")
                print(f"    Success Rate: {pattern['success_rate']:.1%}")
                break

        if found_test:
            print("✓ Test pattern found in list\n")
        else:
            print("❌ Test pattern not found in list\n")
            return False
    else:
        print(f"❌ Failed to list patterns: {data.get('error', 'Unknown error')}\n")
        return False

    # Test 5: Update pattern (upsert)
    print("Test 5: Update Existing Pattern")
    print("-" * 40)

    updated_patterns = test_patterns.copy()
    updated_patterns["image"] = {
        "primary": {
            "type": "css",
            "selector": ".product-image img",
            "confidence": 0.88
        }
    }

    result = await save_pattern_tool({
        "domain": test_domain,
        "patterns": updated_patterns,
        "confidence": 0.94
    })

    data = json.loads(result['content'][0]['text'])

    if data.get("success") and not data.get("created"):
        print("✓ Pattern updated successfully (not created)\n")
    else:
        print(f"❌ Pattern should have been updated, not created\n")
        return False

    # Test 6: Delete pattern (cleanup)
    print("Test 6: Delete Pattern (Cleanup)")
    print("-" * 40)

    result = await delete_pattern_tool({
        "domain": test_domain
    })

    data = json.loads(result['content'][0]['text'])

    if data.get("success"):
        print(f"✓ Pattern deleted successfully")
        print(f"  Deleted count: {data.get('deleted_count', 0)}\n")
    else:
        print(f"❌ Failed to delete pattern: {data.get('error', 'Unknown error')}\n")
        return False

    # Test 7: Verify deletion
    print("Test 7: Verify Deletion")
    print("-" * 40)

    result = await load_pattern_tool({
        "domain": test_domain
    })

    data = json.loads(result['content'][0]['text'])

    if not data.get("success"):
        print("✓ Pattern correctly not found after deletion\n")
    else:
        print("❌ Pattern still exists after deletion\n")
        return False

    # All tests passed
    print("="*60)
    print("✓ ALL TESTS PASSED")
    print("="*60)
    print()
    print("Storage integration with Django database is working correctly!")
    print("Patterns are being saved to and loaded from the shared database.")
    print()

    return True


async def main():
    """Main entry point."""
    try:
        success = await test_storage_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
