from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Address(Base):
    """Saved delivery addresses for users."""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    label = Column(String(50), default="Home")       # Home | Work | Other
    full_name = Column(String(200), nullable=False)
    phone = Column(String(15), nullable=False)
    line1 = Column(String(300), nullable=False)
    line2 = Column(String(300), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    country = Column(String(50), default="India")
    is_default = Column(Integer, default=0)          # 1 = default address
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="addresses")


class Order(Base):
    """
    Order record created after user approves checkout.
    external_order_id is filled after user completes payment on the platform.
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100), index=True, nullable=False)
    search_id = Column(Integer, ForeignKey("search_history.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    # Product snapshot at time of order
    product_name = Column(String(500), nullable=False)
    brand = Column(String(200), nullable=True)
    platform = Column(String(50), nullable=False)
    marketplace_url = Column(Text, nullable=True)       # direct product URL
    cart_url = Column(Text, nullable=True)              # cart/checkout URL
    image_url = Column(Text, nullable=True)

    # Pricing snapshot
    amount = Column(Float, nullable=True)
    original_amount = Column(Float, nullable=True)
    shipping_cost = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=True)         # amount + shipping
    currency = Column(String(10), default="INR")
    discount_percent = Column(Float, nullable=True)

    # Order status
    status = Column(String(50), default="pending_user_action")
    # pending_user_action | payment_in_progress | confirmed | cancelled | failed

    # Filled after user confirms payment on platform
    external_order_id = Column(String(200), nullable=True)
    order_url = Column(Text, nullable=True)             # tracking URL
    expected_delivery = Column(String(200), nullable=True)

    # Delivery address (snapshot)
    delivery_address = Column(JSON, nullable=True)

    # Agent notes
    agent_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="orders")
