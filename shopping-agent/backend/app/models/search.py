from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, func, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class SearchHistory(Base):
    """Stores each user shopping search query and extracted constraints."""
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable = guest users
    session_id = Column(String(100), index=True, nullable=False)       # for guest tracking

    # Raw and parsed query
    raw_query = Column(Text, nullable=False)
    parsed_constraints = Column(JSON, nullable=True)
    # e.g. {"category": "TV", "max_price": 50000, "min_rating": 4.0, "size": "55 inch"}

    # Status of this search
    status = Column(String(50), default="pending")
    # pending | searching | completed | failed

    # Platforms searched
    platforms_searched = Column(JSON, default=list)
    # ["amazon", "flipkart", "meesho", "shopsy", "myntra"]

    # Final result summary stored as JSON
    result_summary = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="searches")
    products = relationship("Product", back_populates="search", cascade="all, delete-orphan")
