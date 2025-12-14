"""Tests for ExtractorPatternAgent."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent import ExtractorPatternAgent


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent can be initialized and cleaned up properly."""
    async with ExtractorPatternAgent() as agent:
        assert agent.client is not None
        assert agent.mcp_server is not None


@pytest.mark.asyncio
async def test_agent_with_custom_config():
    """Test agent initialization with custom configuration."""
    config = {
        "agent": {
            "model": "claude-sonnet-4-5-20250929",
            "max_turns": 10
        },
        "validation": {
            "min_confidence": 0.8
        }
    }

    async with ExtractorPatternAgent(config=config) as agent:
        assert agent.config["agent"]["max_turns"] == 10
        assert agent.config["validation"]["min_confidence"] == 0.8


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real URL and API access")
async def test_generate_patterns():
    """Test pattern generation for a product URL."""
    url = "https://www.example.com/product/test"

    async with ExtractorPatternAgent() as agent:
        patterns = await agent.generate_patterns(url, save_to_db=False)

        # Check basic structure
        assert "patterns" in patterns
        assert isinstance(patterns["patterns"], dict)

        # Check for expected fields
        for field in ["price", "title"]:
            if field in patterns["patterns"]:
                pattern = patterns["patterns"][field]
                assert "primary" in pattern
                assert "type" in pattern["primary"]
                assert "selector" in pattern["primary"]
                assert "confidence" in pattern["primary"]


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires real URL and API access")
async def test_validate_patterns():
    """Test pattern validation."""
    url = "https://www.example.com/product/test"

    test_patterns = {
        "patterns": {
            "price": {
                "primary": {
                    "type": "css",
                    "selector": ".price",
                    "confidence": 0.8
                }
            }
        }
    }

    async with ExtractorPatternAgent() as agent:
        validation = await agent.validate_patterns(url, test_patterns)

        assert "success" in validation
        assert isinstance(validation["success"], bool)


@pytest.mark.asyncio
async def test_custom_query():
    """Test sending custom query to agent."""
    async with ExtractorPatternAgent() as agent:
        result = await agent.query("List all available tools")

        assert result is not None
        assert isinstance(result, dict)


def test_config_loading():
    """Test configuration loading from dict."""
    config = {
        "agent": {"max_turns": 15},
        "browser": {"headless": False}
    }

    agent = ExtractorPatternAgent(config=config)

    assert agent.config["agent"]["max_turns"] == 15
    assert agent.config["browser"]["headless"] is False
    # Default values should still be present
    assert "timeout" in agent.config["agent"]


def test_config_loading_from_file():
    """Test configuration loading from YAML file."""
    config_file = Path(__file__).parent.parent / "config" / "settings.yaml"

    if config_file.exists():
        agent = ExtractorPatternAgent(config_file=str(config_file))

        assert "agent" in agent.config
        assert "browser" in agent.config
        assert "validation" in agent.config


@pytest.mark.asyncio
async def test_agent_context_manager():
    """Test agent works as async context manager."""
    agent = ExtractorPatternAgent()

    # Should not be connected initially
    assert agent.client is None

    async with agent:
        # Should be connected
        assert agent.client is not None

    # Should be disconnected after exit
    # Note: client might still exist but should be disconnected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
