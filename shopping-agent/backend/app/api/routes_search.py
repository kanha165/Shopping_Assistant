"""
Search routes - the core of the application.
Handles shopping queries, streaming updates, search history.
"""
import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db, AsyncSessionLocal
from app.api.deps import get_optional_user, get_required_user
from app.models.user import User
from app.models.search import SearchHistory
from app.models.product import Product
from app.models.agent_log import AgentLog
from app.schemas.search import (
    ShoppingQueryRequest, SearchResponse, SearchHistoryOut,
    AgentStatusUpdate, ParsedConstraints,
)
from app.schemas.product import ProductCompareItem, ReviewSummary
from app.agent.runner import run_shopping_agent, run_shopping_agent_stream
from app.core.logger import app_logger
import time

router = APIRouter(prefix="/search", tags=["Search"])


@router.post("/", response_model=SearchResponse)
async def search_products(
    payload: ShoppingQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Main search endpoint. Runs the full LangGraph agent pipeline.
    Returns complete results when agent finishes.
    Use /search/stream for real-time status updates.
    """
    session_id = payload.session_id or str(uuid.uuid4())
    user_id = current_user.id if current_user else None

    app_logger.info(f"[SearchRoute] Query: '{payload.query}' | session={session_id}")

    # Create search record in DB
    search_record = SearchHistory(
        user_id=user_id,
        session_id=session_id,
        raw_query=payload.query,
        status="searching",
        platforms_searched=[],
    )
    db.add(search_record)
    await db.flush()
    await db.refresh(search_record)
    search_id = search_record.id

    # Log agent start
    await _log_agent_action(
        db, session_id, search_id, user_id,
        "search_started", message=f"Search started: {payload.query}"
    )

    try:
        # Run the agent
        result = await run_shopping_agent(
            query=payload.query,
            session_id=session_id,
            search_id=search_id,
            user_id=user_id,
        )

        # Save products to DB
        saved_products = []
        for p_data in result.get("shortlisted_products", []):
            product = Product(
                search_id=search_id,
                product_name=p_data.get("product_name", ""),
                brand=p_data.get("brand"),
                platform=p_data.get("platform", ""),
                price=p_data.get("price"),
                original_price=p_data.get("original_price"),
                discount_percent=p_data.get("discount_percent"),
                currency=p_data.get("currency", "INR"),
                rating=p_data.get("rating"),
                review_count=p_data.get("review_count"),
                availability=p_data.get("availability", True),
                seller=p_data.get("seller"),
                delivery_info=p_data.get("delivery_info"),
                return_policy=p_data.get("return_policy"),
                image_url=p_data.get("image_url"),
                product_url=p_data.get("product_url", ""),
                specifications=p_data.get("specifications"),
                review_summary=p_data.get("review_summary"),
                rank_score=p_data.get("rank_score"),
                is_shortlisted=p_data.get("is_shortlisted", True),
            )
            db.add(product)
            saved_products.append(product)

        # Update search record
        search_record.status = "completed"
        search_record.platforms_searched = result.get("platforms_searched", [])
        search_record.parsed_constraints = result.get("parsed_constraints")
        search_record.result_summary = {
            "total_products": result.get("total_products_found", 0),
            "shortlisted_count": len(result.get("shortlisted_products", [])),
            "explanation": result.get("agent_explanation", ""),
        }

        await db.commit()

        # Log completion
        await _log_agent_action(
            db, session_id, search_id, user_id,
            "search_completed",
            message=f"Found {result.get('total_products_found', 0)} products",
            output_data={"shortlisted": len(result.get("shortlisted_products", []))}
        )
        await db.commit()   # commit the completion log

        # Build response
        shortlisted_out = [
            _product_dict_to_schema(p) for p in result.get("shortlisted_products", [])
        ]
        all_products_out = [
            _product_dict_to_schema(p) for p in result.get("all_products", [])
        ]

        # Convert raw constraints dict → Pydantic model safely
        raw_constraints = result.get("parsed_constraints") or {}
        try:
            parsed_constraints_out = ParsedConstraints.model_validate(raw_constraints)
        except Exception:
            parsed_constraints_out = None

        return SearchResponse(
            search_id=search_id,
            session_id=session_id,
            raw_query=payload.query,
            parsed_constraints=parsed_constraints_out,
            status="completed",
            platforms_searched=result.get("platforms_searched", []),
            total_products_found=result.get("total_products_found", 0),
            shortlisted_products=shortlisted_out,
            all_products=all_products_out,
            agent_explanation=result.get("agent_explanation"),
            created_at=search_record.created_at,
        )

    except Exception as e:
        search_record.status = "failed"
        await _log_agent_action(
            db, session_id, search_id, user_id,
            "error", status="failed", message=str(e)
        )
        app_logger.error(f"[SearchRoute] Agent failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stream")
async def search_products_stream(
    query: str = Query(min_length=5, max_length=500),
    session_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Streaming search endpoint using Server-Sent Events (SSE).
    Frontend receives real-time status updates as the agent works.

    Usage: EventSource('/api/search/stream?query=...')
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    user_id = current_user.id if current_user else None
    app_logger.info(f"[SearchStream] Query: '{query[:60]}' | session={session_id} | user={user_id}")

    # Save search to DB so it appears in History (same as non-streaming route)
    search_record = SearchHistory(
        user_id=user_id,
        session_id=session_id,
        raw_query=query,
        status="searching",
        platforms_searched=[],
    )
    db.add(search_record)
    await db.flush()
    await db.refresh(search_record)
    search_id = search_record.id
    await db.commit()

    async def event_generator():
        final_result = None

        async def collect_result(events):
            nonlocal final_result
            async for event in events:
                yield event
                # Capture the result event to save to DB
                try:
                    data = json.loads(event.replace("data: ", "").strip())
                    if data.get("type") == "result":
                        final_result = data.get("data")
                except Exception:
                    pass

        async for event in collect_result(
            run_shopping_agent_stream(query=query, session_id=session_id, search_id=search_id)
        ):
            yield event

        # After stream ends, update DB record with results
        if final_result:
            try:
                async with AsyncSessionLocal() as save_db:
                    result_rec = await save_db.execute(
                        select(SearchHistory).where(SearchHistory.id == search_id)
                    )
                    rec = result_rec.scalar_one_or_none()
                    if rec:
                        rec.status = "completed"
                        rec.platforms_searched = final_result.get("platforms_searched", [])
                        rec.parsed_constraints = final_result.get("parsed_constraints")
                        rec.result_summary = {
                            "total_products": final_result.get("total_products_found", 0),
                            "shortlisted_count": len(final_result.get("shortlisted_products", [])),
                            "explanation": final_result.get("agent_explanation", ""),
                        }
                        await save_db.commit()
                        app_logger.info(f"[SearchStream] Saved search #{search_id} to history")
            except Exception as e:
                app_logger.error(f"[SearchStream] Failed to save search history: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/history", response_model=list[SearchHistoryOut])
async def get_search_history(
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get search history for authenticated user or guest session."""
    if current_user:
        # Logged-in: fetch all searches by this user (any session)
        stmt = select(SearchHistory).where(SearchHistory.user_id == current_user.id)
    elif session_id:
        # Guest: fetch by session_id — returns all searches made in this browser session
        stmt = select(SearchHistory).where(SearchHistory.session_id == session_id)
    else:
        return []

    result = await db.execute(
        stmt.order_by(desc(SearchHistory.created_at))
        .limit(limit)
        .offset(offset)
    )
    searches = result.scalars().all()
    return [SearchHistoryOut.model_validate(s) for s in searches]


@router.get("/{search_id}", response_model=SearchResponse)
async def get_search_result(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Get results for a specific search by ID."""
    result = await db.execute(
        select(SearchHistory).where(SearchHistory.id == search_id)
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    # Get products for this search
    products_result = await db.execute(
        select(Product)
        .where(Product.search_id == search_id, Product.is_shortlisted == True)
        .order_by(desc(Product.rank_score))
    )
    products = products_result.scalars().all()

    shortlisted_out = [ProductCompareItem.model_validate(p) for p in products]

    # Convert stored JSON dict → Pydantic model safely
    try:
        parsed_constraints_out = ParsedConstraints.model_validate(search.parsed_constraints) if search.parsed_constraints else None
    except Exception:
        parsed_constraints_out = None

    return SearchResponse(
        search_id=search_id,
        session_id=search.session_id,
        raw_query=search.raw_query,
        parsed_constraints=parsed_constraints_out,
        status=search.status,
        platforms_searched=search.platforms_searched or [],
        total_products_found=len(products),
        shortlisted_products=shortlisted_out,
        all_products=shortlisted_out,
        agent_explanation=search.result_summary.get("explanation") if search.result_summary else None,
        created_at=search.created_at,
    )


@router.delete("/{search_id}", status_code=204)
async def delete_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Delete a search from history (only owner can delete)."""
    result = await db.execute(
        select(SearchHistory).where(
            SearchHistory.id == search_id,
            SearchHistory.user_id == current_user.id,
        )
    )
    search = result.scalar_one_or_none()
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")
    await db.delete(search)
    await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _product_dict_to_schema(p: dict) -> ProductCompareItem:
    """Convert agent product dict to Pydantic schema."""
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


async def _log_agent_action(
    db: AsyncSession,
    session_id: str,
    search_id: int,
    user_id: Optional[int],
    action_type: str,
    status: str = "success",
    message: str = "",
    output_data: Optional[dict] = None,
):
    """Write an agent audit log entry."""
    log = AgentLog(
        user_id=user_id,
        session_id=session_id,
        search_id=search_id,
        action_type=action_type,
        status=status,
        message=message,
        output_data=output_data,
    )
    db.add(log)
    await db.flush()
