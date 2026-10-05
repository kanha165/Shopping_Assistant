"""
Snapdeal scraper using httpx + BeautifulSoup.
"""
import urllib.parse
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.logger import app_logger


class SnapdealScraper(BaseScraper):
    PLATFORM_NAME = "snapdeal"
    BASE_URL = "https://www.snapdeal.com"

    async def search_products(self, query: str, constraints: Dict[str, Any], max_results: int = 5) -> List[Dict[str, Any]]:
        products = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"{self.BASE_URL}/search?keyword={encoded}&santizedQuery={encoded}"
            app_logger.info(f"[Snapdeal] Fetching: {url}")

            soup = await self.fetch_page(url)
            if not soup:
                return []

            cards = soup.select(".product-tuple-listing") or soup.select(".product-tuple-description")
            app_logger.info(f"[Snapdeal] Found {len(cards)} cards")

            for card in cards[:max_results * 2]:
                try:
                    p = self._parse_card(card)
                    if not p:
                        continue
                    max_price = constraints.get("max_price")
                    if max_price and p.get("price") and p["price"] > max_price:
                        continue
                    products.append(p)
                    if len(products) >= max_results:
                        break
                except Exception as e:
                    app_logger.warning(f"[Snapdeal] Card error: {e}")

        except Exception as e:
            app_logger.error(f"[Snapdeal] Search failed: {e}")

        app_logger.info(f"[Snapdeal] Returning {len(products)} products")
        return products

    def _parse_card(self, card) -> Optional[Dict]:
        name_el = card.select_one(".product-title") or card.select_one("p.product-title")
        if not name_el:
            return None
        name = name_el.get_text(strip=True)
        if not name:
            return None

        link_el = card.select_one("a.dp-widget-link") or card.select_one("a[href*='/product/']")
        product_url = link_el.get("href", "") if link_el else ""
        if not product_url:
            return None

        # Price - Snapdeal shows price like "288" not "₹288"
        price_el = card.select_one(".product-price") or card.select_one("span.lfloat.product-price")
        price_text = price_el.get_text(strip=True) if price_el else ""
        # Remove "Rs." prefix
        import re
        price_text = re.sub(r'[Rsr\.\s]', '', price_text)
        price = self.parse_price(price_text)

        orig_el = card.select_one(".product-desc-price.strike")
        original_price = self.parse_price(orig_el.get_text() if orig_el else "")

        # Rating from star width
        rating = None
        rating_el = card.select_one(".filled-stars")
        if rating_el:
            style = rating_el.get("style", "")
            pct = re.findall(r"[\d.]+", style)
            if pct:
                rating = round(float(pct[0]) / 20, 1)

        img_el = card.select_one("img.product-image") or card.select_one("img.main-img-class")
        image_url = img_el.get("src", "") if img_el else ""

        return {
            "product_name": name,
            "brand": self._extract_brand(name),
            "platform": self.PLATFORM_NAME,
            "price": price,
            "original_price": original_price,
            "discount_percent": self.calculate_discount(original_price, price),
            "currency": "INR",
            "rating": rating,
            "review_count": None,
            "availability": True,
            "seller": "Snapdeal",
            "delivery_info": "5-7 days delivery",
            "image_url": image_url,
            "product_url": product_url,
            "specifications": {},
            "return_policy": "7 days return",
        }

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        return {"product_url": product_url, "platform": self.PLATFORM_NAME}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        return []
