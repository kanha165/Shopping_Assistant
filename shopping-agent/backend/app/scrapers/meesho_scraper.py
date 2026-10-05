"""
Meesho scraper.

Strategy (in order of preference):
  1. RapidAPI — if RAPIDAPI_KEY is set in .env (most reliable)
  2. Playwright fallback — tries headless browser (often blocked by Cloudflare)
  3. Returns empty list gracefully — other platforms still work fine

To enable RapidAPI:
  - Sign up free at https://rapidapi.com
  - Search for "Meesho" and subscribe to any unofficial Meesho API
  - Add RAPIDAPI_KEY=your_key to .env
"""
import httpx
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.config import settings
from app.core.logger import app_logger


class MeeshoScraper(BaseScraper):
    PLATFORM_NAME = "meesho"
    BASE_URL = "https://www.meesho.com"

    # ── RapidAPI endpoints (update host/path if your subscribed API differs) ──
    RAPIDAPI_HOST = "meesho-data.p.rapidapi.com"
    RAPIDAPI_SEARCH_URL = "https://meesho-data.p.rapidapi.com/search"

    async def search_products(
        self, query: str, constraints: Dict[str, Any], max_results: int = 5
    ) -> List[Dict[str, Any]]:
        app_logger.info(f"[Meesho] Searching: {query}")

        # Try RapidAPI first if key is configured
        if settings.RAPIDAPI_KEY:
            products = await self._search_via_rapidapi(query, constraints, max_results)
            if products:
                app_logger.info(f"[Meesho] RapidAPI returned {len(products)} products")
                return products[:max_results]
            app_logger.warning("[Meesho] RapidAPI returned no results, trying Playwright fallback")

        # Playwright fallback (often blocked by Meesho's Cloudflare)
        products = await self._search_via_playwright(query, constraints, max_results)
        app_logger.info(f"[Meesho] Returning {len(products)} products")
        return products[:max_results]

    async def _search_via_rapidapi(
        self, query: str, constraints: Dict[str, Any], max_results: int
    ) -> List[Dict[str, Any]]:
        """Fetch Meesho products via RapidAPI."""
        try:
            headers = {
                "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
                "X-RapidAPI-Host": self.RAPIDAPI_HOST,
            }
            params = {"query": query, "page": "1"}

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.RAPIDAPI_SEARCH_URL,
                    headers=headers,
                    params=params,
                )

            if resp.status_code != 200:
                app_logger.warning(f"[Meesho-RapidAPI] HTTP {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            # Most Meesho RapidAPI wrappers return a list or {"products": [...]}
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
            app_logger.error(f"[Meesho-RapidAPI] Error: {e}")
            return []

    def _normalise_rapidapi_item(self, item: dict) -> Optional[Dict]:
        """Normalise a RapidAPI Meesho item into our standard product dict."""
        try:
            name = (
                item.get("name") or item.get("productName") or
                item.get("catalogName") or item.get("title") or ""
            )
            if not name:
                return None

            # Price — various field names across different API providers
            price_raw = (
                item.get("discountedPrice") or item.get("price") or
                item.get("sellingPrice") or item.get("mrp") or 0
            )
            price = float(price_raw) if price_raw else None

            original_raw = item.get("mrp") or item.get("originalPrice") or price_raw
            original = float(original_raw) if original_raw else None

            pid = item.get("id") or item.get("productId") or item.get("catalogId") or ""
            product_url = (
                item.get("url") or item.get("productUrl") or
                item.get("link") or f"https://www.meesho.com/product/{pid}"
            )

            image_url = (
                item.get("imageUrl") or item.get("image") or
                item.get("thumbnail") or ""
            )
            if isinstance(image_url, list):
                image_url = image_url[0] if image_url else ""

            rating = float(item.get("rating") or item.get("avgRating") or 0) or None
            review_count = int(item.get("ratingCount") or item.get("reviews") or 0) or None

            return {
                "product_name": name,
                "brand": item.get("brand") or (name.split()[0] if name else None),
                "platform": "meesho",
                "price": price,
                "original_price": original if original and original != price else None,
                "discount_percent": self.calculate_discount(original, price),
                "currency": "INR",
                "rating": rating,
                "review_count": review_count,
                "availability": True,
                "seller": "Meesho Supplier",
                "delivery_info": "5-7 days delivery",
                "image_url": image_url,
                "product_url": product_url,
                "specifications": {},
                "return_policy": "7 days return",
            }
        except Exception as e:
            app_logger.debug(f"[Meesho] normalise error: {e}")
            return None

    async def _search_via_playwright(
        self, query: str, constraints: Dict[str, Any], max_results: int
    ) -> List[Dict[str, Any]]:
        """Playwright fallback — frequently blocked by Cloudflare."""
        try:
            from app.scrapers.playwright_runner import run_in_playwright, _scrape_meesho
            products = await run_in_playwright(_scrape_meesho, query, max_results) or []
            max_price = constraints.get("max_price")
            if max_price:
                products = [p for p in products if not p.get("price") or p["price"] <= max_price]
            return products
        except Exception as e:
            app_logger.warning(f"[Meesho] Playwright fallback failed: {e}")
            return []

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        return {"product_url": product_url, "platform": self.PLATFORM_NAME}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        return []
