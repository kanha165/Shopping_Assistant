from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ProductBase(BaseModel):
    """Core product schema - matches the normalized DB structure."""
    product_name: str
    brand: Optional[str] = None
    platform: str
    price: Optional[float] = None
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    review_count: Optional[int] = None
    availability: bool = True
    seller: Optional[str] = None
    delivery_info: Optional[str] = None
    return_policy: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    specifications: Optional[Dict[str, Any]] = None


class ProductCreate(ProductBase):
    search_id: int


class ReviewSummary(BaseModel):
    """Matches keys returned by analyze_reviews_tool in tools.py."""
    overall_sentiment: Optional[str] = None
    pros: List[str] = []                    # LLM returns 'pros' not 'positive_themes'
    cons: List[str] = []                    # LLM returns 'cons' not 'negative_themes'
    defects_mentioned: List[str] = []
    value_for_money: Optional[str] = None
    delivery_feedback: Optional[str] = None
    build_quality: Optional[str] = None
    review_confidence: Optional[float] = None
    review_summary: Optional[str] = None    # 2-sentence summary from LLM
    note: Optional[str] = None              # e.g. "reviews_unavailable" or "fallback_rule_based"


class ProductOut(ProductBase):
    id: int
    search_id: int
    review_summary: Optional[ReviewSummary] = None
    rank_score: Optional[float] = None
    is_shortlisted: bool = False
    cart_status: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductCompareItem(BaseModel):
    """Lightweight product card for comparison view."""
    id: int
    product_name: str
    brand: Optional[str] = None
    platform: str
    price: Optional[float] = None
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    delivery_info: Optional[str] = None
    image_url: Optional[str] = None
    product_url: str
    rank_score: Optional[float] = None
    is_shortlisted: bool = False
    review_summary: Optional[ReviewSummary] = None

    model_config = {"from_attributes": True}
