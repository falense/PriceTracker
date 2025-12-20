"""Data models for PriceFetcher."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatternSelector(BaseModel):
    """Single pattern selector configuration."""

    type: str  # "css", "xpath", "jsonld", "meta"
    selector: str
    attribute: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class FieldPattern(BaseModel):
    """Pattern for extracting a single field."""

    primary: PatternSelector
    fallbacks: List[PatternSelector] = Field(default_factory=list)


class ExtractionPattern(BaseModel):
    """Complete extraction pattern for a domain."""

    store_domain: str
    patterns: Dict[str, FieldPattern]  # "price", "title", "availability", "image"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Product(BaseModel):
    """Product to fetch prices for."""

    product_id: str
    url: str
    domain: str
    name: Optional[str] = None
    current_price: Optional[Decimal] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    check_interval: int = 3600  # seconds
    last_checked: Optional[datetime] = None
    active: bool = True
    priority: str = "normal"
    listing_id: Optional[str] = None  # ProductListing UUID for multi-store support


class ExtractedField(BaseModel):
    """Result of extracting a single field."""

    value: Optional[str] = None
    method: Optional[str] = None  # Which extraction method worked
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    """Complete extraction result for a product."""

    price: ExtractedField
    title: Optional[ExtractedField] = None
    availability: Optional[ExtractedField] = None
    image: Optional[ExtractedField] = None
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of validating an extraction."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class FetchResult(BaseModel):
    """Result of fetching a product price."""

    product_id: str
    url: str
    success: bool
    extraction: Optional[ExtractionResult] = None
    validation: Optional[ValidationResult] = None
    error: Optional[str] = None
    duration_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FetchSummary(BaseModel):
    """Summary of a fetch run."""

    total: int
    success: int
    failed: int
    products: List[FetchResult]
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
