"""
Agent activity log routes - for the agent status panel in the UI.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.agent_log import AgentLog
from app.schemas.agent import AgentLogOut

router = APIRouter(prefix="/agent", tags=["Agent Logs"])


@router.get("/logs/{session_id}", response_model=list[AgentLogOut])
async def get_session_logs(
    session_id: str,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get all agent activity logs for a session. Used by the UI activity panel."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == session_id)
        .order_by(AgentLog.created_at)
        .limit(limit)
    )
    logs = result.scalars().all()
    return [AgentLogOut.model_validate(log) for log in logs]


@router.get("/logs/search/{search_id}", response_model=list[AgentLogOut])
async def get_search_logs(
    search_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get all agent logs for a specific search."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.search_id == search_id)
        .order_by(AgentLog.created_at)
    )
    logs = result.scalars().all()
    return [AgentLogOut.model_validate(log) for log in logs]


@router.get("/status/{session_id}")
async def get_agent_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the latest status for an active agent session."""
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.session_id == session_id)
        .order_by(desc(AgentLog.created_at))
        .limit(1)
    )
    log = result.scalar_one_or_none()
    if not log:
        return {"status": "not_found", "message": "No activity for this session"}

    return {
        "session_id": session_id,
        "latest_action": log.action_type,
        "status": log.status,
        "message": log.message,
        "timestamp": log.created_at,
    }


# ── Agent Workflow Endpoints ──────────────────────────────────────────────────

@router.post("/search")
async def agent_search(payload: dict, db: AsyncSession = Depends(get_db)):
    """POST /agent/search — execute full shopping agent pipeline."""
    from app.agent.runner import run_shopping_agent
    query = payload.get("query", "")
    session_id = payload.get("session_id")
    result = await run_shopping_agent(query=query, session_id=session_id)
    return result


@router.post("/approve")
async def agent_approve(payload: dict, db: AsyncSession = Depends(get_db)):
    """POST /agent/approve — human approval before checkout."""
    session_id = payload.get("session_id")
    product_name = payload.get("product_name")
    marketplace = payload.get("marketplace") or payload.get("platform")
    confirmed = payload.get("confirmed", True)

    if not confirmed:
        return {
            "session_id": session_id,
            "status": "cancelled",
            "message": "User cancelled purchase approval.",
        }

    return {
        "session_id": session_id,
        "status": "approved",
        "product_name": product_name,
        "marketplace": marketplace,
        "next_step": "checkout",
        "message": "User approved purchase. Proceeding to cart & checkout.",
    }


@router.post("/cart")
async def agent_cart(payload: dict):
    """POST /agent/cart — prepare marketplace cart link."""
    from app.agent.cart_handler import add_to_cart
    platform = payload.get("marketplace") or payload.get("platform", "amazon")
    product_url = payload.get("product_url", "")
    res = await add_to_cart(platform, product_url)
    return res


@router.post("/checkout")
async def agent_checkout(payload: dict):
    """POST /agent/checkout — prepare checkout breakdown."""
    marketplace = payload.get("marketplace") or payload.get("platform", "amazon")
    price = payload.get("price", 0.0)
    shipping = payload.get("shipping_cost", 0.0)
    total = price + shipping
    return {
        "marketplace": marketplace,
        "product_name": payload.get("product_name"),
        "price": price,
        "shipping_cost": shipping,
        "total_amount": total,
        "delivery_info": payload.get("delivery_info", "2-4 days"),
        "status": "awaiting_payment_handoff",
        "requires_user_confirmation": True,
    }


@router.post("/payment-handoff")
async def agent_payment_handoff(payload: dict):
    """POST /agent/payment-handoff — handoff control to user for payment."""
    marketplace = payload.get("marketplace") or payload.get("platform", "amazon")
    cart_url = payload.get("cart_url") or payload.get("product_url", "")
    return {
        "status": "payment_handoff",
        "marketplace": marketplace,
        "payment_url": cart_url,
        "message": "Agent has prepared checkout. User must complete payment authorization.",
        "security_note": "Agent never collects or stores PIN, CVV, OTP, or payment credentials.",
    }

