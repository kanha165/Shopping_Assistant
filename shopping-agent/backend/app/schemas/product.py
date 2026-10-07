from pydantic import BaseModel
from typing import Optional, List


class ReviewSummary(BaseModel):
    overall_sentiment: Optional[str] = None
    pros: List[str] = []
    cons: List[str] = []
    defects_mentioned: List[str] = []
    value_for_money: Optional[str] = None
    delivery_feedback: Optional[str] = None
    build_quality: Optional[str] = None
    review_confidence: Optional[float] = None
    review_summary: Optional[str] = None
    note: Optional[str] = None


class ProductCompareItem(BaseModel):
    id: int = 0
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
