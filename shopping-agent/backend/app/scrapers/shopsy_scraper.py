"""
Shopsy scraper - Shopsy is a separate app by Flipkart targeting price-sensitive buyers.
It has its own search endpoint at shopsy.in. Products are tagged as "shopsy" correctly.
Note: Shopsy product URLs point to shopsy.in, NOT flipkart.com — avoiding duplicate
products between the two platforms in deduplication.
"""
import urllib.parse
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.logger import app_logger


class ShopsyScraper(BaseScraper):
    PLATFORM_NAME = "shopsy"
    BASE_URL = "https://www.shopsy.in"

    async def search_products(self, query: str, constraints: Dict[str, Any], max_results: int = 5) -> List[Dict[str, Any]]:
        products = []
        try:
            encoded = urllib.parse.quote_plus(query)
            # Use shopsy.in search directly — keeps URLs on shopsy.in domain
            # so deduplication can distinguish these from flipkart.com products
            url = f"{self.BASE_URL}/search?q={encoded}&otracker=search"
            app_logger.info(f"[Shopsy] Fetching: {url}")

            soup = await self.fetch_page(url)
            if not soup:
                app_logger.warning("[Shopsy] No page returned — platform may be unavailable")
                return []

            cards = (
                soup.select("div._1AtVbE div._13oc-S") or
                soup.select("div[data-id]") or
                soup.select("._2kHMtA")
            )
            app_logger.info(f"[Shopsy] Found {len(cards)} cards")

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
                    app_logger.warning(f"[Shopsy] Card error: {e}")

        except Exception as e:
            app_logger.error(f"[Shopsy] Search failed: {e}")

        app_logger.info(f"[Shopsy] Returning {len(products)} products")
        return products

    def _parse_card(self, card) -> Optional[Dict]:
        name_el = (
            card.select_one("._4rR01T") or
            card.select_one(".s1Q9rs") or
            card.select_one("a[title]")
        )
        if not name_el:
            return None
        name = name_el.get_text(strip=True) or name_el.get("title", "")
        if not name:
            return None

        link_el = card.select_one("a._1fQZEK") or card.select_one("a[href*='/p/']") or card.select_one("a")
        href = link_el.get("href", "") if link_el else ""

        # Always build URL on shopsy.in so it is distinct from flipkart.com URLs.
        # This prevents the deduplication engine from merging shopsy & flipkart results.
        if href.startswith("/"):
            product_url = f"{self.BASE_URL}{href}"
        elif href.startswith("http"):
            # Replace flipkart.com domain with shopsy.in if present
            product_url = href.replace("www.flipkart.com", "www.shopsy.in")
        else:
            return None  # skip cards with no usable URL

        price_el = card.select_one("._30jeq3") or card.select_one("._1_WHN1")
        price = self.parse_price(price_el.get_text() if price_el else "")

        orig_el = card.select_one("._3I9_wc")
        original_price = self.parse_price(orig_el.get_text() if orig_el else "")

        rating_el = card.select_one("._3LWZlK")
        rating = self.parse_rating(rating_el.get_text() if rating_el else "")

        review_el = card.select_one("._2_R_DZ span")
        review_count = self.parse_review_count(review_el.get_text() if review_el else "")

        img_el = card.select_one("img")
        image_url = img_el.get("src", "") if img_el else ""

        return {
            "product_name": name,
            "brand": self._extract_brand(name),
            "platform": self.PLATFORM_NAME,   # always "shopsy"
            "price": price,
            "original_price": original_price,
            "discount_percent": self.calculate_discount(original_price, price),
            "currency": "INR",
            "rating": rating,
            "review_count": review_count,
            "availability": True,
            "seller": "Shopsy",
            "delivery_info": "4-6 days delivery",
            "image_url": image_url,
            "product_url": product_url,
            "specifications": {},
            "return_policy": "7 days return",
        }

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        return {"product_url": product_url, "platform": self.PLATFORM_NAME}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        return []
