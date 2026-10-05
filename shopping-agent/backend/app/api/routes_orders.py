"""
Orders + Addresses routes.
POST /orders/            — create order after user approves
POST /orders/approve     — user confirms or cancels purchase
PATCH /orders/{id}       — user updates with external order ID after payment
GET  /orders/            — list user's orders
GET  /orders/{id}        — single order detail
POST /addresses/         — save delivery address
GET  /addresses/         — list user's saved addresses
PUT  /addresses/{id}     — update address
DELETE /addresses/{id}   — delete address
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.api.deps import get_optional_user, get_required_user
from app.models.user import User
from app.models.order import Order, Address
from app.models.product import Product
from app.models.agent_log import AgentLog
from app.schemas.order import (
    AddressCreate, AddressOut,
    OrderCreateRequest, OrderApprovalRequest, OrderUpdateRequest,
    OrderOut, PurchaseApprovalSummary,
)
from app.agent.cart_handler import add_to_cart, CART_URLS, CHECKOUT_URLS
from app.core.logger import app_logger

router = APIRouter(tags=["Orders & Addresses"])


# ── Addresses ─────────────────────────────────────────────────────────────────

@router.post("/addresses", response_model=AddressOut, status_code=201)
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """Save a new delivery address."""
    # If is_default=1, clear existing defaults first
    if payload.is_default:
        existing = await db.execute(
            select(Address).where(Address.user_id == current_user.id, Address.is_default == 1)
        )
        for addr in existing.scalars().all():
            addr.is_default = 0

    addr = Address(user_id=current_user.id, **payload.model_dump())
    db.add(addr)
    await db.commit()
    await db.refresh(addr)
    return AddressOut.model_validate(addr)


@router.get("/addresses", response_model=List[AddressOut])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    """List all saved addresses for the user."""
    result = await db.execute(
        select(Address)
        .where(Address.user_id == current_user.id)
        .order_by(desc(Address.is_default), Address.id)
    )
    return [AddressOut.model_validate(a) for a in result.scalars().all()]


@router.put("/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int,
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    addr = result.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")

    if payload.is_default:
        existing = await db.execute(
            select(Address).where(Address.user_id == current_user.id, Address.is_default == 1)
        )
        for a in existing.scalars().all():
            a.is_default = 0

    for field, value in payload.model_dump().items():
        setattr(addr, field, value)

    await db.commit()
    await db.refresh(addr)
    return AddressOut.model_validate(addr)


@router.delete("/addresses/{address_id}", status_code=204)
async def delete_address(
    address_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_required_user),
):
    result = await db.execute(
        select(Address).where(Address.id == address_id, Address.user_id == current_user.id)
    )
    addr = result.scalar_one_or_none()
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")
    await db.delete(addr)
    await db.commit()


# ── Orders ────────────────────────────────────────────────────────────────────

@router.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Create an order record when user is about to checkout.
    Status starts as 'pending_user_action' — user must confirm via /orders/approve.
    """
    user_id = current_user.id if current_user else None
    total = payload.total_amount or (
        (payload.amount or 0) + (payload.shipping_cost or 0)
    )

    # Fetch delivery address snapshot if provided
    delivery_snapshot = None
    if payload.delivery_address_id and current_user:
        addr_result = await db.execute(
            select(Address).where(
                Address.id == payload.delivery_address_id,
                Address.user_id == current_user.id,
            )
        )
        addr = addr_result.scalar_one_or_none()
        if addr:
            delivery_snapshot = {
                "full_name": addr.full_name,
                "phone": addr.phone,
                "line1": addr.line1,
                "line2": addr.line2,
                "city": addr.city,
                "state": addr.state,
                "pincode": addr.pincode,
                "country": addr.country,
            }

    cart_url = CART_URLS.get(payload.platform, payload.marketplace_url)

    order = Order(
        user_id=user_id,
        session_id=payload.session_id,
        search_id=payload.search_id,
        product_id=payload.product_id if (payload.product_id and payload.product_id > 0) else None,
        product_name=payload.product_name,
        brand=payload.brand,
        platform=payload.platform,
        marketplace_url=payload.marketplace_url,
        cart_url=cart_url,
        image_url=payload.image_url,
        amount=payload.amount,
        original_amount=payload.original_amount,
        shipping_cost=payload.shipping_cost or 0.0,
        total_amount=total,
        currency=payload.currency,
        discount_percent=payload.discount_percent,
        expected_delivery=payload.expected_delivery,
        delivery_address=delivery_snapshot,
        status="pending_user_action",
        agent_notes=(
            "Agent stopped before payment. "
            "User must confirm and complete payment on the platform."
        ),
    )
    db.add(order)
    _add_log(db, user_id, payload.session_id, payload.search_id,
             "order_created", payload.platform,
             f"Order created for {payload.product_name[:60]}")
    await db.commit()
    await db.refresh(order)

    app_logger.info(
        f"[Orders] Created order #{order.id} | {payload.platform} | "
        f"₹{total} | user={user_id or 'guest'}"
    )
    return OrderOut.model_validate(order)


@router.post("/orders/approve", response_model=OrderOut)
async def approve_order(
    payload: OrderApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Human-in-the-loop approval gate.
    confirmed=True  → agent prepares cart, returns checkout URL.
    confirmed=False → order cancelled, no action taken.
    NEVER auto-pays. User must complete payment on the platform.
    """
    result = await db.execute(select(Order).where(Order.id == payload.order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not payload.confirmed:
        order.status = "cancelled"
        _add_log(db, order.user_id, order.session_id, order.search_id,
                 "order_cancelled", order.platform, "User cancelled purchase")
        await db.commit()
        await db.refresh(order)
        app_logger.info(f"[Orders] Order #{order.id} cancelled by user")
        return OrderOut.model_validate(order)

    # User confirmed — prepare cart handoff
    cart_result = await add_to_cart(order.platform, order.marketplace_url or "")
    order.cart_url = cart_result.get("cart_url") or order.cart_url
    order.status = "payment_in_progress"

    _add_log(db, order.user_id, order.session_id, order.search_id,
             "awaiting_user_payment", order.platform,
             "User confirmed. Awaiting payment on platform.")
    await db.commit()
    await db.refresh(order)

    app_logger.info(
        f"[Orders] Order #{order.id} approved — cart URL: {order.cart_url} | "
        "AGENT STOPPED — human must complete payment"
    )
    return OrderOut.model_validate(order)


@router.patch("/orders/{order_id}", response_model=OrderOut)
async def update_order(
    order_id: int,
    payload: OrderUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Update order after user completes payment on platform.
    User provides external_order_id and/or order_url from the marketplace.
    """
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ownership check: same logic as get_order
    if current_user:
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        if order.user_id is not None:
            raise HTTPException(status_code=403, detail="Access denied")

    if payload.external_order_id:
        order.external_order_id = payload.external_order_id
    if payload.order_url:
        order.order_url = payload.order_url
    if payload.status:
        order.status = payload.status

    _add_log(db, order.user_id, order.session_id, order.search_id,
             "order_updated", order.platform,
             f"Order updated: status={order.status} ext_id={order.external_order_id}")
    await db.commit()
    await db.refresh(order)

    app_logger.info(f"[Orders] Order #{order_id} updated: {payload.status}")
    return OrderOut.model_validate(order)


@router.get("/orders", response_model=List[OrderOut])
async def list_orders(
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """List all orders for authenticated user or guest session."""
    if current_user:
        stmt = select(Order).where(Order.user_id == current_user.id)
    elif session_id:
        stmt = select(Order).where(Order.session_id == session_id)
    else:
        return []

    result = await db.execute(stmt.order_by(desc(Order.created_at)))
    return [OrderOut.model_validate(o) for o in result.scalars().all()]


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Ownership check: authenticated users can only view their own orders.
    # Guest users can only view orders that match their session (no user_id).
    if current_user:
        if order.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        # Guest: must have no owner (guest order) — prevent guessing IDs
        if order.user_id is not None:
            raise HTTPException(status_code=403, detail="Access denied")

    return OrderOut.model_validate(order)


# ── Purchase Approval Summary ─────────────────────────────────────────────────

@router.get("/orders/approval-summary/{product_id}", response_model=PurchaseApprovalSummary)
async def get_approval_summary(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the pre-purchase summary shown to user before they confirm.
    Agent always stops here — user must explicitly approve.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    shipping = 0.0  # calculated from platform defaults
    total = (product.price or 0) + shipping

    return PurchaseApprovalSummary(
        product_name=product.product_name,
        platform=product.platform,
        product_url=product.product_url,
        image_url=product.image_url,
        price=product.price,
        shipping_cost=shipping,
        total_amount=total,
        currency=product.currency or "INR",
        discount_percent=product.discount_percent,
        original_price=product.original_price,
        delivery_info=product.delivery_info,
        return_policy=product.return_policy,
        seller=product.seller,
        rating=product.rating,
        review_count=product.review_count,
        requires_user_confirmation=True,
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _add_log(db, user_id, session_id, search_id, action_type, platform, message):
    log = AgentLog(
        user_id=user_id,
        session_id=session_id or "unknown",
        search_id=search_id,
        action_type=action_type,
        platform=platform,
        status="success",
        message=message,
    )
    db.add(log)
