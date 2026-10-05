"""
Base scraper - uses httpx + BeautifulSoup for fast async scraping.
No Playwright needed for search pages (avoids event loop conflicts with FastAPI).
Playwright only used for cart/checkout operations.
"""
import asyncio
import random
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import httpx
from bs4 import BeautifulSoup
from app.core.config import settings
from app.core.logger import app_logger


class BaseScraper(ABC):
    PLATFORM_NAME: str = "base"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    async def fetch_page(self, url: str, retries: int = 2) -> Optional[BeautifulSoup]:
        """Fetch a URL and return BeautifulSoup object."""
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(
                    headers=self._get_headers(),
                    timeout=20,
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        return BeautifulSoup(resp.text, "lxml")
                    app_logger.warning(f"[{self.PLATFORM_NAME}] HTTP {resp.status_code} for {url[:60]}")
            except Exception as e:
                app_logger.warning(f"[{self.PLATFORM_NAME}] Fetch attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1)
        return None

    async def random_delay(self, extra: float = 0.0):
        delay = random.uniform(0.5 + extra, 1.5 + extra)
        await asyncio.sleep(delay)

    def parse_price(self, price_text: str) -> Optional[float]:
        if not price_text:
            return None
        try:
            import re
            # Remove currency symbol, spaces
            cleaned = price_text.replace("₹", "").replace(" ", "").strip()
            # Remove ALL commas — Indian format uses commas as thousand separators
            cleaned = cleaned.replace(",", "")
            # Extract first valid number only
            numeric = re.findall(r"^\d+\.?\d*", cleaned)
            if not numeric:
                # fallback: find first number anywhere
                numeric = re.findall(r"\d+\.?\d*", cleaned)
            if numeric:
                val = float(numeric[0])
                # Sanity check: no real Indian e-commerce product costs more than ₹50 lakh
                # Values above this are scraper artifacts (concatenated price text)
                if val > 5_000_000:
                    return None
                return val
        except Exception:
            pass
        return None

    def parse_rating(self, rating_text: str) -> Optional[float]:
        if not rating_text:
            return None
        try:
            import re
            numeric = re.findall(r"\d+\.?\d*", rating_text)
            if numeric:
                val = float(numeric[0])
                if val <= 5.0:
                    return val
        except Exception:
            pass
        return None

    def parse_review_count(self, text: str) -> Optional[int]:
        if not text:
            return None
        try:
            import re
            text = text.lower().replace(",", "")
            if "k" in text:
                num = re.findall(r"[\d.]+", text)
                if num:
                    return int(float(num[0]) * 1000)
            nums = re.findall(r"\d+", text)
            if nums:
                return int(nums[0])
        except Exception:
            pass
        return None

    def calculate_discount(self, original: Optional[float], current: Optional[float]) -> Optional[float]:
        if original and current and original > current:
            return round(((original - current) / original) * 100, 1)
        return None

    def _extract_brand(self, product_name: str) -> Optional[str]:
        if not product_name:
            return None
        known_brands = [
            "Samsung", "LG", "Sony", "OnePlus", "Xiaomi", "Redmi", "Realme",
            "Apple", "Nokia", "Motorola", "Vivo", "Oppo", "Boat", "JBL",
            "Philips", "Bajaj", "Havells", "Whirlpool", "Voltas", "Daikin",
            "Nike", "Adidas", "Puma", "Beardo", "WOW", "Mamaearth", "HP", "Dell",
            "Lenovo", "Asus", "Acer", "MSI", "MacBook", "TCL", "Hisense", "Vu",
        ]
        for brand in known_brands:
            if brand.lower() in product_name.lower():
                return brand
        return product_name.split()[0] if product_name else None

    @abstractmethod
    async def search_products(self, query: str, constraints: Dict[str, Any], max_results: int = 5) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        return {"url": product_url, "product_url": product_url, "marketplace": self.PLATFORM_NAME}

    async def check_availability(self, product_url: str) -> bool:
        details = await self.get_product_details(product_url)
        return details.get("availability", True)

    async def get_price(self, product_url: str) -> Optional[float]:
        details = await self.get_product_details(product_url)
        return details.get("price")

    async def get_shipping(self, product_url: str) -> float:
        return 0.0

    async def add_to_cart(self, product_url: str) -> Dict[str, Any]:
        from app.agent.cart_handler import add_to_cart
        return await add_to_cart(self.PLATFORM_NAME, product_url)

    async def get_cart(self) -> Dict[str, Any]:
        from app.agent.cart_handler import CART_URLS
        return {"cart_url": CART_URLS.get(self.PLATFORM_NAME, ""), "marketplace": self.PLATFORM_NAME}

    async def checkout(self, product_url: str, address: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from app.agent.cart_handler import CHECKOUT_URLS
        return {
            "status": "payment_handoff_required",
            "marketplace": self.PLATFORM_NAME,
            "checkout_url": CHECKOUT_URLS.get(self.PLATFORM_NAME, product_url),
            "address": address,
            "requires_user_payment": True,
        }

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        return []


# MarketplaceAdapter interface alias
MarketplaceAdapter = BaseScraper
BaseMarketplace = BaseScraper

