"""
Flipkart scraper using httpx + BeautifulSoup.
"""
import urllib.parse
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.logger import app_logger


class FlipkartScraper(BaseScraper):
    PLATFORM_NAME = "flipkart"
    BASE_URL = "https://www.flipkart.com"

    async def search_products(self, query: str, constraints: Dict[str, Any], max_results: int = 5) -> List[Dict[str, Any]]:
        products = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"{self.BASE_URL}/search?q={encoded}&otracker=search"
            app_logger.info(f"[Flipkart] Fetching: {url}")

            soup = await self.fetch_page(url)
            if not soup:
                app_logger.warning("[Flipkart] No page returned")
                return []

            # Flipkart uses multiple possible card selectors
            cards = (
                soup.select("div._1AtVbE div._13oc-S") or
                soup.select("div[data-id]") or
                soup.select("._2kHMtA") or
                soup.select("._1xHGtK._373qXS") or
                soup.select("div._2B099V")
            )
            app_logger.info(f"[Flipkart] Found {len(cards)} cards")

            for card in cards[:max_results * 3]:
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
                    app_logger.warning(f"[Flipkart] Card error: {e}")

        except Exception as e:
            app_logger.error(f"[Flipkart] Search failed: {e}")

        app_logger.info(f"[Flipkart] Returning {len(products)} products")
        return products

    def _parse_card(self, card) -> Optional[Dict[str, Any]]:
        # Product name - actual class from debug: RG5Slk
        name_el = (
            card.select_one(".RG5Slk") or
            card.select_one("._4rR01T") or
            card.select_one(".s1Q9rs") or
            card.select_one("a[title]")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True) or name_el.get("title", "")
        if not name:
            return None

        # URL - actual class from debug: k7wcnx
        link_el = card.select_one("a.k7wcnx") or card.select_one("a[href*='/p/']") or card.select_one("a")
        href = link_el.get("href", "") if link_el else ""
        product_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
        if not product_url or "flipkart.com" not in product_url:
            return None

        # Price - actual class: oFEPlD or hZ3P6w
        price_el = (
            card.select_one(".oFEPlD") or
            card.select_one(".hZ3P6w") or
            card.select_one("._30jeq3") or
            card.select_one(".Nx9bqj")
        )
        price = self.parse_price(price_el.get_text() if price_el else "")

        # Original price
        orig_el = card.select_one("._3I9_wc") or card.select_one(".yRaY8j")
        original_price = self.parse_price(orig_el.get_text() if orig_el else "")

        # Rating - actual class: CjyrHS
        rating_el = card.select_one(".CjyrHS") or card.select_one("._3LWZlK")
        rating = self.parse_rating(rating_el.get_text() if rating_el else "")

        # Review count - actual class: PvbNSB or PvbNMB
        review_el = (
            card.select_one(".PvbNMB") or
            card.select_one("._2_R_DZ span") or
            card.select_one(".PvbNSB")
        )
        review_count = self.parse_review_count(review_el.get_text() if review_el else "")

        # Image — try multiple selectors + data-src for lazy loading
        img_el = (
            card.select_one("img.UCc1lI") or
            card.select_one("img.PZfbSE") or
            card.select_one("img._396cs4") or
            card.select_one("img[src*='rukminim']") or   # Flipkart CDN URL pattern
            card.select_one("img")
        )
        image_url = ""
        if img_el:
            image_url = (
                img_el.get("src") or
                img_el.get("data-src") or ""
            )
            # Skip tiny placeholder images
            if image_url and ("placeholder" in image_url or "blank" in image_url or len(image_url) < 20):
                image_url = ""

        # Discount
        disc_el = card.select_one("._3Ay6Sb span") or card.select_one(".UkUFwK span")
        discount_text = disc_el.get_text() if disc_el else ""
        discount_percent = None
        if "%" in discount_text:
            import re
            nums = re.findall(r"\d+", discount_text)
            discount_percent = float(nums[0]) if nums else None

        return {
            "product_name": name,
            "brand": self._extract_brand(name),
            "platform": self.PLATFORM_NAME,
            "price": price,
            "original_price": original_price,
            "discount_percent": discount_percent or self.calculate_discount(original_price, price),
            "currency": "INR",
            "rating": rating,
            "review_count": review_count,
            "availability": True,
            "seller": "Flipkart",
            "delivery_info": "Check on Flipkart",
            "image_url": image_url,
            "product_url": product_url,
            "specifications": {},
            "return_policy": "7 days return",
        }

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        try:
            soup = await self.fetch_page(product_url)
            if not soup:
                return {}
            title = soup.select_one(".B_NuCI")
            price_el = soup.select_one("._30jeq3._16Jk6d")
            return {
                "product_name": title.get_text(strip=True) if title else "",
                "platform": self.PLATFORM_NAME,
                "price": self.parse_price(price_el.get_text() if price_el else ""),
                "product_url": product_url,
                "specifications": {},
            }
        except Exception as e:
            app_logger.error(f"[Flipkart] Detail error: {e}")
            return {}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        try:
            soup = await self.fetch_page(product_url)
            if not soup:
                return []
            reviews = []
            for el in soup.select("._6K-7Co")[:max_reviews]:
                text = el.get_text(strip=True)
                if text and len(text) > 20:
                    reviews.append(text)
            return reviews
        except Exception as e:
            app_logger.error(f"[Flipkart] Reviews error: {e}")
            return []
