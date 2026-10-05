"""
Playwright runner in a separate thread to avoid event loop conflicts with FastAPI.
Uses concurrent.futures.ThreadPoolExecutor to run sync playwright.
"""
import asyncio
import atexit
import concurrent.futures
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logger import app_logger

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)


def _shutdown_executor():
    """Gracefully shut down the thread pool at process exit."""
    app_logger.info("[PlaywrightRunner] Shutting down thread pool executor")
    _executor.shutdown(wait=True)


# Register cleanup so threads are not left dangling on app exit
atexit.register(_shutdown_executor)


def _run_playwright_sync(func, *args, **kwargs):
    """Run a sync playwright function in a thread pool."""
    from playwright.sync_api import sync_playwright
    import random

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=settings.PLAYWRIGHT_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1920, "height": 1080},
            locale="en-IN",
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
        )
        page = context.new_page()
        page.set_default_timeout(settings.PLAYWRIGHT_TIMEOUT)
        try:
            result = func(page, *args, **kwargs)
        finally:
            context.close()
            browser.close()
        return result


async def run_in_playwright(func, *args, **kwargs):
    """Async wrapper - runs playwright sync function in thread pool."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            _executor,
            lambda: _run_playwright_sync(func, *args, **kwargs)
        )
        return result
    except Exception as e:
        app_logger.error(f"[PlaywrightRunner] Error: {e}")
        return None


# ── Meesho scraper function ───────────────────────────────────────────────────

def _scrape_meesho(page, query: str, max_results: int) -> List[Dict]:
    import urllib.parse, json, re
    products = []
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.meesho.com/search?q={encoded}&searchType=manual&searchIdentifier=text_search"
        page.goto(url, wait_until="networkidle", timeout=25000)
        # Use Playwright's built-in wait instead of time.sleep() so the thread
        # is not blocked while the JS finishes rendering
        page.wait_for_timeout(2000)

        # Try to get __NEXT_DATA__
        content = page.content()
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            props = data.get("props", {}).get("pageProps", {})

            def find_list(obj, depth=0):
                if depth > 8: return []
                if isinstance(obj, list) and len(obj) > 0:
                    first = obj[0]
                    if isinstance(first, dict) and any(k in first for k in ["name", "catalogName", "id"]):
                        return obj
                if isinstance(obj, dict):
                    for v in obj.values():
                        result = find_list(v, depth + 1)
                        if result:
                            return result
                return []

            items = find_list(props)
            app_logger.info(f"[Meesho-PW] Found {len(items)} items in NEXT_DATA")

            for item in items[:max_results]:
                p = _parse_meesho_item(item)
                if p:
                    products.append(p)

        # DOM fallback
        if not products:
            cards = page.query_selector_all('[data-testid="product-container"]')
            app_logger.info(f"[Meesho-PW] DOM cards: {len(cards)}")
            for card in cards[:max_results]:
                try:
                    name_el = card.query_selector('[data-testid="product-name"]') or card.query_selector("p")
                    name = name_el.inner_text().strip() if name_el else ""
                    if not name:
                        continue
                    link_el = card.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""
                    product_url = f"https://www.meesho.com{href}" if href and href.startswith("/") else href or "https://www.meesho.com"
                    price_el = card.query_selector("h5")
                    price_text = price_el.inner_text() if price_el else ""
                    price = _parse_price(price_text)
                    img_el = card.query_selector("img")
                    image_url = img_el.get_attribute("src") if img_el else ""
                    products.append({
                        "product_name": name,
                        "brand": name.split()[0],
                        "platform": "meesho",
                        "price": price,
                        "original_price": None,
                        "discount_percent": None,
                        "currency": "INR",
                        "rating": None,
                        "review_count": None,
                        "availability": True,
                        "seller": "Meesho Supplier",
                        "delivery_info": "5-7 days delivery",
                        "image_url": image_url,
                        "product_url": product_url,
                        "specifications": {},
                        "return_policy": "7 days return",
                    })
                except Exception:
                    continue

    except Exception as e:
        app_logger.error(f"[Meesho-PW] Scrape error: {e}")
    return products


# ── Myntra scraper function ───────────────────────────────────────────────────

def _scrape_myntra(page, query: str, max_results: int) -> List[Dict]:
    import urllib.parse, json, re
    products = []
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.myntra.com/{encoded}"
        page.goto(url, wait_until="networkidle", timeout=25000)
        # Use Playwright's built-in wait instead of time.sleep()
        page.wait_for_timeout(2000)

        content = page.content()

        # Try NEXT_DATA
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            # Find products in data
            def find_products(obj, depth=0):
                if depth > 8: return []
                if isinstance(obj, list) and len(obj) > 0:
                    first = obj[0]
                    if isinstance(first, dict) and any(k in first for k in ["productId", "productDisplayName"]):
                        return obj
                if isinstance(obj, dict):
                    for v in obj.values():
                        r = find_products(v, depth + 1)
                        if r: return r
                return []
            items = find_products(data)
            app_logger.info(f"[Myntra-PW] Found {len(items)} items in NEXT_DATA")
            for item in items[:max_results]:
                p = _parse_myntra_item(item)
                if p:
                    products.append(p)

        # DOM fallback
        if not products:
            cards = page.query_selector_all("li.product-base")
            app_logger.info(f"[Myntra-PW] DOM cards: {len(cards)}")
            for card in cards[:max_results]:
                try:
                    brand_el = card.query_selector("h3.product-brand")
                    name_el = card.query_selector("h4.product-product")
                    brand = brand_el.inner_text().strip() if brand_el else ""
                    name = name_el.inner_text().strip() if name_el else ""
                    full_name = f"{brand} {name}".strip()
                    if not full_name:
                        continue
                    link_el = card.query_selector("a")
                    href = link_el.get_attribute("href") if link_el else ""
                    product_url = f"https://www.myntra.com/{href}" if href and not href.startswith("http") else href or "https://www.myntra.com"
                    price_el = card.query_selector("span.product-discountedPrice") or card.query_selector("div.product-price span")
                    price = _parse_price(price_el.inner_text() if price_el else "")
                    img_el = card.query_selector("img")
                    image_url = img_el.get_attribute("src") if img_el else ""
                    products.append({
                        "product_name": full_name,
                        "brand": brand or None,
                        "platform": "myntra",
                        "price": price,
                        "original_price": None,
                        "discount_percent": None,
                        "currency": "INR",
                        "rating": None,
                        "review_count": None,
                        "availability": True,
                        "seller": "Myntra",
                        "delivery_info": "3-5 days delivery",
                        "image_url": image_url,
                        "product_url": product_url,
                        "specifications": {},
                        "return_policy": "30 days easy return",
                    })
                except Exception:
                    continue

    except Exception as e:
        app_logger.error(f"[Myntra-PW] Scrape error: {e}")
    return products


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(text: str) -> Optional[float]:
    import re
    if not text: return None
    cleaned = text.replace("₹", "").replace(",", "").strip()
    nums = re.findall(r"[\d.]+", cleaned)
    return float(nums[0]) if nums else None


def _parse_meesho_item(item: dict) -> Optional[Dict]:
    try:
        name = item.get("name") or item.get("catalogName") or item.get("product_name") or ""
        if not name: return None
        price_info = item.get("priceInfo") or item.get("price") or {}
        price = float(price_info.get("discountedPrice") or price_info.get("mrp") or 0) if isinstance(price_info, dict) else float(price_info or 0)
        original = float(price_info.get("mrp") or 0) if isinstance(price_info, dict) else None
        pid = item.get("id") or item.get("catalogId") or ""
        product_url = item.get("url") or f"https://www.meesho.com/product/{pid}"
        media = item.get("media") or {}
        images = media.get("images") or item.get("images") or []
        image_url = (images[0].get("url") if isinstance(images[0], dict) else images[0]) if images else ""
        rating_data = item.get("rating") or {}
        rating = float(rating_data.get("avgRating") or 0) if isinstance(rating_data, dict) else None
        review_count = int(rating_data.get("ratingCount") or 0) if isinstance(rating_data, dict) else None
        return {
            "product_name": name, "brand": item.get("brand") or name.split()[0],
            "platform": "meesho", "price": price or None, "original_price": original or None,
            "discount_percent": None, "currency": "INR",
            "rating": rating or None, "review_count": review_count or None,
            "availability": True, "seller": "Meesho Supplier",
            "delivery_info": "5-7 days delivery", "image_url": image_url,
            "product_url": product_url, "specifications": {}, "return_policy": "7 days return",
        }
    except Exception:
        return None


def _parse_myntra_item(item: dict) -> Optional[Dict]:
    try:
        brand = item.get("brand", {})
        brand_name = brand.get("name", "") if isinstance(brand, dict) else str(brand or "")
        name = (item.get("productDisplayName") or item.get("name") or f"{brand_name} Product").strip()
        if not name or name == "Product": return None
        pid = item.get("productId") or ""
        slug = item.get("landingPageUrl") or ""
        product_url = f"https://www.myntra.com/{slug}" if slug and not slug.startswith("http") else slug or f"https://www.myntra.com/{pid}"
        prices = item.get("price") or {}
        price = float(prices.get("discounted") or prices.get("mrp") or 0) if isinstance(prices, dict) else None
        original = float(prices.get("mrp") or 0) if isinstance(prices, dict) else None
        images = item.get("images") or [{}]
        image_url = (images[0].get("secureSrc") or images[0].get("src", "")) if isinstance(images[0], dict) else (images[0] if isinstance(images[0], str) else "")
        return {
            "product_name": name, "brand": brand_name or None,
            "platform": "myntra", "price": price or None, "original_price": original or None,
            "discount_percent": None, "currency": "INR",
            "rating": float(item.get("rating") or 0) or None,
            "review_count": int(item.get("ratingCount") or 0) or None,
            "availability": True, "seller": "Myntra",
            "delivery_info": "3-5 days delivery", "image_url": image_url,
            "product_url": product_url, "specifications": {}, "return_policy": "30 days easy return",
        }
    except Exception:
        return None
