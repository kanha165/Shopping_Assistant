from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class ShoppingQueryRequest(BaseModel):
    query: str = Field(min_length=5, max_length=500)
    session_id: Optional[str] = None


class ParsedConstraints(BaseModel):
    category: Optional[str] = None
    brand: Optional[str] = None
    product: Optional[str] = None
    model: Optional[str] = None
    storage: Optional[str] = None
    ram: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    budget: Optional[float] = None
    currency: str = "INR"
    min_rating: Optional[float] = None
    min_reviews: Optional[int] = None
    condition: Optional[str] = None
    delivery_days: Optional[int] = None
    priority: Optional[str] = None
    keywords: Optional[List[str]] = None
    specifications: Optional[Dict[str, Any]] = None
    other: Optional[Dict[str, Any]] = None
