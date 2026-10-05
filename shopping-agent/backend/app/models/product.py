from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, ForeignKey, JSON, Text, func
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class Product(Base):
    """
    Normalized product data collected from any platform.
    One row per product per search.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    search_id = Column(Integer, ForeignKey("search_history.id"), nullable=False)

    # Core product info
    product_name = Column(String(500), nullable=False)
    brand = Column(String(200), nullable=True)
    platform = Column(String(50), nullable=False)
    # "amazon" | "flipkart" | "meesho" | "shopsy" | "myntra" | "snapdeal" | "ajio"

    # Pricing
    price = Column(Float, nullable=True)
    original_price = Column(Float, nullable=True)   # MRP before discount
    discount_percent = Column(Float, nullable=True)
    currency = Column(String(10), default="INR")

    # Ratings & Reviews
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)

    # Availability & Delivery
    availability = Column(Boolean, default=True)
    seller = Column(String(200), nullable=True)
    delivery_info = Column(String(300), nullable=True)
    return_policy = Column(String(300), nullable=True)

    # Product detail
    image_url = Column(Text, nullable=True)
    product_url = Column(Text, nullable=False)
    specifications = Column(JSON, nullable=True)
    # e.g. {"screen_size": "55 inch", "resolution": "4K", "refresh_rate": "60Hz"}

    # Review Analysis (filled after review fetch)
    review_summary = Column(JSON, nullable=True)
    # {
    #   "overall_sentiment": "positive",
    #   "positive_themes": ["great picture", "easy setup"],
    #   "negative_themes": ["remote feels cheap"],
    #   "defects_mentioned": [],
    #   "value_for_money": "good"
    # }

    # Ranking score computed by comparison engine
    rank_score = Column(Float, nullable=True)
    is_shortlisted = Column(Boolean, default=False)

    # Cart/checkout state for this product
    cart_status = Column(String(50), nullable=True)
    # None | "added_to_cart" | "checkout_initiated" | "awaiting_payment"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    search = relationship("SearchHistory", back_populates="products")
