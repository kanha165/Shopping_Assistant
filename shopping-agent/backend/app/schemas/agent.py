from pydantic import BaseModel
from typing import Optional, Any, List, Dict
from datetime import datetime


class AgentLogOut(BaseModel):
    """Agent audit log entry - shown in UI as agent activity feed."""
    id: int
    session_id: str
    action_type: str
    platform: Optional[str] = None
    tool_name: Optional[str] = None
    status: str
    message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentState(BaseModel):
    """
    Internal LangGraph state object.
    Passed between every node in the graph.
    """
    session_id: str
    search_id: Optional[int] = None
    raw_query: str
    parsed_constraints: Optional[Dict[str, Any]] = None

    # Collected products from all platforms
    collected_products: List[Dict[str, Any]] = []

    # After filtering & ranking
    shortlisted_products: List[Dict[str, Any]] = []

    # Agent messages / conversation
    messages: List[Any] = []

    # Current step tracker
    current_step: str = "start"
    # start → parse_query → search → extract_details → analyze_reviews
    # → compare → shortlist → present → await_selection → cart → checkout → end

    # Errors collected during execution
    errors: List[str] = []

    # Final explanation from LLM
    agent_explanation: Optional[str] = None

    # Selected product (after user picks one)
    selected_product_id: Optional[int] = None

    # Platforms successfully searched
    platforms_searched: List[str] = []

    # Flag: did agent reach checkout (needs human)
    awaiting_payment: bool = False
