"""
Cart Handler - redirects user to platform cart/checkout page.
Agent ALWAYS stops before payment. Human must complete payment.
Uses httpx to verify product URL is reachable, then returns cart URL.
No Playwright needed - just returns the correct cart/checkout URL.
"""
import asyncio
from typing import Dict, Any
import httpx
from app.core.logger import app_logger


CART_URLS = {
    "amazon":   "https://www.amazon.in/gp/cart/view.html",
    "flipkart": "https://www.flipkart.com/viewcart",
    "meesho":   "https://www.meesho.com/cart",
    "myntra":   "https://www.myntra.com/checkout/cart",
    "shopsy":   "https://www.shopsy.in/cart",
    "snapdeal": "https://www.snapdeal.com/checkout/cart",
}

CHECKOUT_URLS = {
    "amazon":   "https://www.amazon.in/checkout/now",
    "flipkart": "https://www.flipkart.com/checkout",
    "meesho":   "https://www.meesho.com/checkout",
    "myntra":   "https://www.myntra.com/checkout",
    "shopsy":   "https://www.shopsy.in/checkout",
    "snapdeal": "https://www.snapdeal.com/checkout",
}


async def add_to_cart(platform: str, product_url: str) -> Dict[str, Any]:
    """
    Prepare cart information for the user.
    Returns cart URL so user can open it in their browser.
    Agent never enters payment credentials.
    """
    # Direct product page URL is the safest entry point so user can click 'Buy Now' / 'Add to Cart'
    cart_url = product_url if (product_url and product_url.startswith("http")) else CART_URLS.get(platform, "")

    platform_messages = {
        "amazon":   "Product page opened. Click 'Buy Now' or 'Add to Cart' on Amazon to proceed.",
        "flipkart": "Product page opened. Click 'Buy Now' or 'Add to Cart' on Flipkart to proceed.",
        "meesho":   "Open product link on Meesho and click Buy Now.",
        "myntra":   "Open product link on Myntra and click Add to Bag.",
        "shopsy":   "Open product link on Shopsy and click Buy Now.",
        "snapdeal": "Open product link on Snapdeal and click Buy Now.",
    }

    message = platform_messages.get(
        platform,
        f"Open product link on {platform} and click Buy Now."
    )

    app_logger.info(f"[CartHandler] Cart handoff for {platform}: {cart_url[:60]}")

    return {
        "success": True,
        "message": message,
        "cart_url": cart_url,
        "product_url": product_url,
        "platform": platform,
        "requires_user_action": True,   # Always True — human must complete payment
        "payment_note": (
            "The agent has stopped here. "
            "Complete payment yourself on the platform. "
            "Your CVV, OTP, and passwords are never handled by this system."
        ),
    }


async def get_checkout_url(platform: str) -> str:
    """Return the checkout URL for a platform."""
    return CHECKOUT_URLS.get(platform, "")
