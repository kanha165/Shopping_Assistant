from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class AgentLog(Base):
    """
    Audit log of every action the agent takes.
    Required for transparency and debugging.
    """
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100), index=True, nullable=False)
    search_id = Column(Integer, ForeignKey("search_history.id"), nullable=True)

    # What happened
    action_type = Column(String(100), nullable=False)
    # Examples:
    # "query_parsed" | "search_started" | "product_found" | "review_fetched"
    # "comparison_done" | "shortlist_created" | "cart_add" | "checkout_initiated"
    # "awaiting_user_approval" | "error"

    platform = Column(String(50), nullable=True)   # which platform this action was on
    tool_name = Column(String(100), nullable=True)  # which LangGraph tool was called
    status = Column(String(50), default="success")  # success | failed | skipped

    # Details
    message = Column(Text, nullable=True)
    input_data = Column(JSON, nullable=True)   # what was sent to the tool
    output_data = Column(JSON, nullable=True)  # what the tool returned

    # Timing
    duration_ms = Column(Integer, nullable=True)   # how long the action took
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="agent_logs")
