"""ExtractorPatternAgent - Web scraping pattern generator package."""

# Lazy import to avoid loading heavy dependencies until needed
def __getattr__(name):
    if name == "PatternGenerator":
        from .src.pattern_generator import PatternGenerator
        return PatternGenerator
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__version__ = "0.2.0"
__all__ = ["PatternGenerator"]
