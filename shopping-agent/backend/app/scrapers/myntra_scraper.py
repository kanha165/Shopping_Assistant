"""
Myntra scraper.

Strategy (in order of preference):
  1. RapidAPI — if RAPIDAPI_KEY is set in .env (most reliable)
  2. Playwright fallback — tries headless browser (often blocked + login wall)
  3. Returns empty list gracefully — other platforms still work fine

To enable RapidAPI:
  - Sign up free at https://rapidapi.com
  - Search for "Myntra" and subscribe to any unofficial Myntra API
  - Add RAPIDAPI_KEY=your_key to .env
"""
import httpx
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.config import settings
from app.core.logger import app_logger


class MyntraScraper(BaseScraper):
    PLATFORM_NAME = "myntra"
    BASE_URL = "https://www.myntra.com"

    # ── RapidAPI endpoints (update host/path if your subscribed API differs) ──
    RAPIDAPI_HOST = "myntra-unofficial.p.rapidapi.com"
    RAPIDAPI_SEARCH_URL = "https://myntra-unofficial.p.rapidapi.com/products"

    async def search_products(
        self, query: str, constraints: Dict[str, Any], max_results: int = 5
    ) -> List[Dict[str, Any]]:
        app_logger.info(f"[Myntra] Searching: {query}")

        # Try RapidAPI first if key is configured
        if settings.RAPIDAPI_KEY:
            products = await self._search_via_rapidapi(query, constraints, max_results)
            if products:
                app_logger.info(f"[Myntra] RapidAPI returned {len(products)} products")
                return products[:max_results]
            app_logger.warning("[Myntra] RapidAPI returned no results, trying Playwright fallback")

        # Playwright fallback (login wall + bot detection often blocks this)
        products = await self._search_via_playwright(query, constraints, max_results)
        app_logger.info(f"[Myntra] Returning {len(products)} products")
        return products[:max_results]

    async def _search_via_rapidapi(
        self, query: str, constraints: Dict[str, Any], max_results: int
    ) -> List[Dict[str, Any]]:
        """Fetch Myntra products via RapidAPI."""
        try:
            headers = {
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": self.RAPIDAPI_HOST,
            }
            params = {"keyword": query, "page": "1", "rows": str(max_results * 2)}

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.RAPIDAPI_SEARCH_URL,
                    headers=headers,
                    params=params,
                )

            if resp.status_code != 200:
                app_logger.warning(f"[Myntra-RapidAPI] HTTP {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            # Most Myntra RapidAPI wrappers return {"products": [...]} or a list
            raw = data if isinstance(data, list) else data.get("products", data.get("data", []))
            if not isinstance(raw, list):
                return []

            products = []
            max_price = constraints.get("max_price")

            for item in raw[:max_results * 2]:
                p = self._normalise_rapidapi_item(item)
                if not p:
                    continue
                if max_price and p.get("price") and p["price"] > max_price:
                    continue
                products.append(p)
                if len(products) >= max_results:
                    break

            return products

        except Exception as e:
            app_logger.error(f"[Myntra-RapidAPI] Error: {e}")
            return []

    def _normalise_rapidapi_item(self, item: dict) -> Optional[Dict]:
        """Normalise a RapidAPI Myntra item into our standard product dict."""
        try:
            # Various field names used by different API providers
            name = (
                item.get("productDisplayName") or item.get("name") or
                item.get("title") or item.get("productName") or ""
            )
            if not name:
                return None

            brand_raw = item.get("brand") or {}
            brand = (
                brand_raw.get("name") if isinstance(brand_raw, dict)
                else str(brand_raw) if brand_raw
                else item.get("brandName") or None
            )

            price_raw = (
                item.get("price") or item.get("discountedPrice") or
                item.get("sellingPrice") or {}
            )
            if isinstance(price_raw, dict):
                price = float(price_raw.get("discounted") or price_raw.get("mrp") or 0) or None
                original = float(price_raw.get("mrp") or 0) or None
            else:
                price = float(price_raw) if price_raw else None
                original = float(item.get("mrp") or item.get("originalPrice") or 0) or None

            pid = item.get("productId") or item.get("id") or ""
            slug = item.get("landingPageUrl") or item.get("slug") or ""
            if slug and not slug.startswith("http"):
                product_url = f"https://www.myntra.com/{slug}"
            elif slug:
                product_url = slug
            else:
                product_url = f"https://www.myntra.com/{pid}"

            images = item.get("images") or item.get("media") or [{}]
            first_img = images[0] if images else {}
            if isinstance(first_img, dict):
                image_url = first_img.get("secureSrc") or first_img.get("src") or ""
            else:
                image_url = str(first_img) if first_img else ""

            rating = float(item.get("rating") or item.get("ratingValue") or 0) or None
            review_count = int(item.get("ratingCount") or item.get("reviewCount") or 0) or None

            return {
                "product_name": name,
                "brand": brand,
                "platform": "myntra",
                "price": price,
                "original_price": original if original and original != price else None,
                "discount_percent": self.calculate_discount(original, price),
                "currency": "INR",
                "rating": rating,
                "review_count": review_count,
                "availability": True,
                "seller": "Myntra",
                "delivery_info": "3-5 days delivery",
                "image_url": image_url,
                "product_url": product_url,
                "specifications": {},
                "return_policy": "30 days easy return",
            }
        except Exception as e:
            app_logger.debug(f"[Myntra] normalise error: {e}")
            return None

    async def _search_via_playwright(
        self, query: str, constraints: Dict[str, Any], max_results: int
    ) -> List[Dict[str, Any]]:
        """Playwright fallback — login wall + bot detection blocks this often."""
        try:
            from app.scrapers.playwright_runner import run_in_playwright, _scrape_myntra
            products = await run_in_playwright(_scrape_myntra, query, max_results) or []
            max_price = constraints.get("max_price")
            if max_price:
                products = [p for p in products if not p.get("price") or p["price"] <= max_price]
            return products
        except Exception as e:
            app_logger.warning(f"[Myntra] Playwright fallback failed: {e}")
            return []

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        return {"product_url": product_url, "platform": self.PLATFORM_NAME}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        return []
