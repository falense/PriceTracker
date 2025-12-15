"""ExtractorPatternAgent - AI-powered web scraping pattern generator."""

# Lazy imports to avoid loading heavy dependencies
def __getattr__(name):
    if name == "ExtractorPatternAgent":
        from .agent import ExtractorPatternAgent
        return ExtractorPatternAgent
    elif name == "PatternGenerator":
        from .pattern_generator import PatternGenerator
        return PatternGenerator
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__version__ = "0.1.0"
__all__ = ["ExtractorPatternAgent", "PatternGenerator"]
