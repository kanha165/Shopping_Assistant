"""
Search routes — stateless, no DB, no auth required.
Anyone can search and get results directly.
"""
import uuid
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas.search import ShoppingQueryRequest, ParsedConstraints
from app.schemas.product import ProductCompareItem, ReviewSummary
from app.agent.runner import run_shopping_agent, run_shopping_agent_stream
from app.core.logger import app_logger

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/")
async def search_products(payload: ShoppingQueryRequest):
    """
    Main search endpoint — no login required.
    Runs full LangGraph agent and returns results.
    """
    session_id = payload.session_id or str(uuid.uuid4())
    app_logger.info(f"[SearchRoute] Query: '{payload.query}' | session={session_id}")

    result = await run_shopping_agent(
        query=payload.query,
        session_id=session_id,
    )

    shortlisted_out = [_to_schema(p) for p in result.get("shortlisted_products", [])]
    all_products_out = [_to_schema(p) for p in result.get("all_products", [])]

    raw_constraints = result.get("parsed_constraints") or {}
    try:
        parsed_constraints_out = ParsedConstraints.model_validate(raw_constraints)
    except Exception:
        parsed_constraints_out = None

    return {
        "session_id": session_id,
        "raw_query": payload.query,
        "parsed_constraints": parsed_constraints_out,
        "status": result.get("status", "completed"),
        "platforms_searched": result.get("platforms_searched", []),
        "platform_status": result.get("platform_status", {}),
        "total_products_found": result.get("total_products_found", 0),
        "shortlisted_products": shortlisted_out,
        "all_products": all_products_out,
        "agent_explanation": result.get("agent_explanation"),
    }


@router.get("/stream")
async def search_products_stream(
    query: str = Query(min_length=5, max_length=500),
    session_id: str = Query(default=None),
):
    """
    Streaming search — Server-Sent Events, no login required.
    Usage: EventSource('/api/search/stream?query=...')
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    app_logger.info(f"[SearchStream] Query: '{query[:60]}' | session={session_id}")

    async def event_generator():
        async for event in run_shopping_agent_stream(query=query, session_id=session_id):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_schema(p: dict) -> ProductCompareItem:
    review_summary = None
    if p.get("review_summary"):
        try:
            review_summary = ReviewSummary(**p["review_summary"])
        except Exception:
            pass
    return ProductCompareItem(
        id=p.get("id", 0),
        product_name=p.get("product_name", ""),
        brand=p.get("brand"),
        platform=p.get("platform", ""),
        price=p.get("price"),
        original_price=p.get("original_price"),
        discount_percent=p.get("discount_percent"),
        rating=p.get("rating"),
        review_count=p.get("review_count"),
        delivery_info=p.get("delivery_info"),
        image_url=p.get("image_url"),
        product_url=p.get("product_url", ""),
        rank_score=p.get("rank_score"),
        is_shortlisted=p.get("is_shortlisted", False),
        review_summary=review_summary,
    )
