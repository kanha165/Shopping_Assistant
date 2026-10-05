from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


# ── Address ───────────────────────────────────────────────────────────────────

class AddressCreate(BaseModel):
    label: str = "Home"
    full_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=10, max_length=15)
    line1: str = Field(min_length=5, max_length=300)
    line2: Optional[str] = None
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str = Field(min_length=6, max_length=10)
    country: str = "India"
    is_default: int = 0


class AddressOut(AddressCreate):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderCreateRequest(BaseModel):
    """Frontend sends this when user clicks Confirm Purchase."""
    session_id: str
    search_id: Optional[int] = None
    product_id: Optional[int] = None

    # Product snapshot
    product_name: str
    brand: Optional[str] = None
    platform: str
    marketplace_url: str
    image_url: Optional[str] = None

    # Pricing snapshot
    amount: Optional[float] = None
    original_amount: Optional[float] = None
    shipping_cost: float = 0.0
    total_amount: Optional[float] = None
    currency: str = "INR"
    discount_percent: Optional[float] = None

    # Delivery
    delivery_address_id: Optional[int] = None
    expected_delivery: Optional[str] = None


class OrderApprovalRequest(BaseModel):
    """User explicitly approves the purchase."""
    order_id: int
    confirmed: bool  # True = proceed, False = cancel


class OrderUpdateRequest(BaseModel):
    """After user completes payment on platform, they can update order with external ID."""
    external_order_id: Optional[str] = None
    order_url: Optional[str] = None
    status: Optional[str] = None  # confirmed | cancelled | failed


class OrderOut(BaseModel):
    id: int
    session_id: str
    search_id: Optional[int] = None
    product_id: Optional[int] = None

    product_name: str
    brand: Optional[str] = None
    platform: str
    marketplace_url: Optional[str] = None
    cart_url: Optional[str] = None
    image_url: Optional[str] = None

    amount: Optional[float] = None
    original_amount: Optional[float] = None
    shipping_cost: float = 0.0
    total_amount: Optional[float] = None
    currency: str = "INR"
    discount_percent: Optional[float] = None

    status: str
    external_order_id: Optional[str] = None
    order_url: Optional[str] = None
    expected_delivery: Optional[str] = None
    delivery_address: Optional[Dict[str, Any]] = None
    agent_notes: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Purchase Approval Flow ────────────────────────────────────────────────────

class PurchaseApprovalSummary(BaseModel):
    """
    Shown to user BEFORE confirming purchase.
    Agent stops here — user must click Confirm.
    """
    product_name: str
    platform: str
    product_url: str
    image_url: Optional[str] = None

    price: Optional[float] = None
    shipping_cost: float = 0.0
    total_amount: Optional[float] = None
    currency: str = "INR"
    discount_percent: Optional[float] = None
    original_price: Optional[float] = None

    delivery_info: Optional[str] = None
    return_policy: Optional[str] = None
    seller: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None

    requires_user_confirmation: bool = True
    payment_note: str = (
        "The agent will stop after cart. "
        "You must complete payment yourself. "
        "CVV, OTP, and PIN are never handled by this system."
    )
