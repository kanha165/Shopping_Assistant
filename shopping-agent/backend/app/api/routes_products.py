"""
Product routes - individual product details, cart, checkout.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.api.deps import get_optional_user
from app.models.product import Product
from app.models.agent_log import AgentLog
from app.schemas.product import ProductOut
from app.schemas.search import CartRequest, CartResponse, CheckoutHandoffResponse
from app.agent.cart_handler import add_to_cart
from app.models.user import User
from app.core.logger import app_logger

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get full details for a specific product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)


@router.get("/search/{search_id}/all")
async def get_all_products_for_search(
    search_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get ALL products (not just shortlisted) for a search."""
    result = await db.execute(
        select(Product)
        .where(Product.search_id == search_id)
        .order_by(desc(Product.rank_score))
    )
    products = result.scalars().all()
    return [ProductOut.model_validate(p) for p in products]


@router.post("/cart/add", response_model=CartResponse)
async def add_product_to_cart(
    payload: CartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Add a selected product to cart using browser automation.
    The agent ALWAYS stops before payment - human must complete checkout.
    """
    # Fetch product from DB
    result = await db.execute(select(Product).where(Product.id == payload.product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    app_logger.info(
        f"[CartRoute] Adding to cart: {product.product_name[:40]} | "
        f"platform={product.platform} | user={current_user.id if current_user else 'guest'}"
    )

    # Add to cart via Playwright
    cart_result = await add_to_cart(product.platform, product.product_url)

    # Update product cart status in DB
    product.cart_status = "added_to_cart" if cart_result.get("success") else "cart_failed"

    # Log cart action
    log = AgentLog(
        user_id=current_user.id if current_user else None,
        session_id=payload.session_id,
        search_id=payload.search_id,
        action_type="cart_add",
        platform=product.platform,
        status="success" if cart_result.get("success") else "failed",
        message=cart_result.get("message", ""),
        output_data=cart_result,
    )
    db.add(log)
    await db.commit()

    return CartResponse(
        success=cart_result.get("success", False),
        message=cart_result.get("message", ""),
        cart_url=cart_result.get("cart_url"),
        product_id=payload.product_id,
        requires_user_action=True,  # Always True - human must complete payment
    )


@router.post("/checkout/handoff/{product_id}", response_model=CheckoutHandoffResponse)
async def checkout_handoff(
    product_id: int,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Navigate to checkout page and return the URL to the user.
    Agent STOPS here. Human must complete payment.
    CVV, OTP, passwords are NEVER handled by the agent.
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build checkout URL based on platform
    checkout_urls = {
        "amazon": "https://www.amazon.in/checkout/now",
        "flipkart": "https://www.flipkart.com/checkout",
        "myntra": "https://www.myntra.com/checkout/cart",
        "meesho": product.product_url,
        "shopsy": "https://www.shopsy.in/checkout",
        "snapdeal": "https://www.snapdeal.com/checkout",
    }
    checkout_url = checkout_urls.get(product.platform, product.product_url)

    # Update product status
    product.cart_status = "checkout_initiated"

    # Log checkout handoff
    log = AgentLog(
        user_id=current_user.id if current_user else None,
        session_id=session_id,
        search_id=product.search_id,
        action_type="checkout_initiated",
        platform=product.platform,
        status="success",
        message="Checkout page reached. Awaiting human approval for payment.",
    )
    db.add(log)
    await db.commit()

    app_logger.info(
        f"[CheckoutRoute] Handoff for product {product_id} | platform={product.platform} | "
        "AGENT STOPPED - human must complete payment"
    )

    return CheckoutHandoffResponse(
        success=True,
        message="Checkout page is ready. Please complete the payment manually.",
        checkout_url=checkout_url,
        product_id=product_id,
        platform=product.platform,
        requires_payment_approval=True,
        instructions=(
            "The AI agent has stopped here. "
            "Please open the checkout URL, log in if needed, "
            "and complete the payment yourself. "
            "Your CVV, OTP, and password are never handled by this system."
        ),
    )
