from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.schemas.product import ProductCompareItem


# ── Request ──────────────────────────────────────────────────────────────────

class ShoppingQueryRequest(BaseModel):
    """What the user sends from the frontend chat box."""
    query: str = Field(
        min_length=5,
        max_length=500,
        examples=["Find a 55 inch 4K TV under 50000 rupees with good reviews"]
    )
    session_id: Optional[str] = None  # auto-generated on frontend if not provided
    user_id: Optional[int] = None     # None for guest users


class ParsedConstraints(BaseModel):
    """LLM-extracted structured constraints from the raw query."""
    category: Optional[str] = None
    brand: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: str = "INR"
    min_rating: Optional[float] = None
    min_reviews: Optional[int] = None
    size: Optional[str] = None
    color: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    delivery_days: Optional[int] = None      # max acceptable delivery days
    platforms: Optional[List[str]] = None    # specific platforms to search
    keywords: Optional[List[str]] = None     # extra keywords extracted
    other: Optional[Dict[str, Any]] = None   # anything else


# ── Response ─────────────────────────────────────────────────────────────────

class AgentStatusUpdate(BaseModel):
    """Streamed status updates during agent execution."""
    type: str           # "status" | "product" | "error" | "done" | "thinking"
    message: str
    platform: Optional[str] = None
    data: Optional[Any] = None


class SearchResponse(BaseModel):
    """Final response after agent completes search."""
    search_id: int
    session_id: str
    raw_query: str
    parsed_constraints: Optional[ParsedConstraints] = None
    status: str
    platforms_searched: List[str] = []
    total_products_found: int = 0
    shortlisted_products: List[ProductCompareItem] = []
    all_products: List[ProductCompareItem] = []
    agent_explanation: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchHistoryOut(BaseModel):
    id: int
    session_id: str
    raw_query: str
    parsed_constraints: Optional[Dict[str, Any]] = None
    status: str
    platforms_searched: List[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Cart & Checkout ───────────────────────────────────────────────────────────

class CartRequest(BaseModel):
    product_id: int
    search_id: int
    session_id: str


class CartResponse(BaseModel):
    success: bool
    message: str
    cart_url: Optional[str] = None
    product_id: int
    requires_user_action: bool = False   # True = need human to complete payment


class CheckoutHandoffResponse(BaseModel):
    """
    Returned when agent reaches payment step.
    Agent STOPS here - human must complete payment.
    """
    success: bool
    message: str
    checkout_url: Optional[str] = None
    product_id: int
    platform: str
    requires_payment_approval: bool = True   # Always True - we never auto-pay
    instructions: str = "Please complete the payment manually. The agent has paused."
