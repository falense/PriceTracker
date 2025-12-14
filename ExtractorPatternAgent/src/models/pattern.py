"""Data models for extraction patterns."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class SelectorType(str, Enum):
    """Types of selectors supported."""
    CSS = "css"
    XPATH = "xpath"
    JSONLD = "jsonld"
    META = "meta"


@dataclass
class SelectorPattern:
    """A single selector pattern with metadata."""
    type: SelectorType
    selector: str
    confidence: float
    attribute: Optional[str] = None
    post_process: Optional[str] = None  # e.g., "strip", "lower", "extract_number"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "type": self.type.value,
            "selector": self.selector,
            "confidence": self.confidence,
        }
        if self.attribute:
            result["attribute"] = self.attribute
        if self.post_process:
            result["post_process"] = self.post_process
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectorPattern":
        """Create from dictionary."""
        return cls(
            type=SelectorType(data["type"]),
            selector=data["selector"],
            confidence=data["confidence"],
            attribute=data.get("attribute"),
            post_process=data.get("post_process"),
        )


@dataclass
class FieldPattern:
    """Pattern for extracting a specific field with fallbacks."""
    primary: SelectorPattern
    fallbacks: List[SelectorPattern] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "primary": self.primary.to_dict(),
            "fallbacks": [fb.to_dict() for fb in self.fallbacks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FieldPattern":
        """Create from dictionary."""
        return cls(
            primary=SelectorPattern.from_dict(data["primary"]),
            fallbacks=[SelectorPattern.from_dict(fb) for fb in data.get("fallbacks", [])],
        )


@dataclass
class Pattern:
    """Complete extraction pattern for a domain."""
    store_domain: str
    patterns: Dict[str, FieldPattern]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "store_domain": self.store_domain,
            "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pattern":
        """Create from dictionary."""
        return cls(
            store_domain=data["store_domain"],
            patterns={k: FieldPattern.from_dict(v) for k, v in data["patterns"].items()},
            metadata=data.get("metadata", {}),
        )


@dataclass
class PatternResult:
    """Result from pattern generation or validation."""
    success: bool
    pattern: Optional[Pattern] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    execution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if self.pattern:
            result["pattern"] = self.pattern.to_dict()
        if self.execution_time:
            result["execution_time"] = self.execution_time
        return result
