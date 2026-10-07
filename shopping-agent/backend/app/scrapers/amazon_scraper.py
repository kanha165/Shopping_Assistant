"""
Amazon India scraper using httpx + BeautifulSoup.
"""
import urllib.parse
from typing import List, Dict, Any, Optional
from app.scrapers.base_scraper import BaseScraper
from app.core.logger import app_logger


class AmazonScraper(BaseScraper):
    PLATFORM_NAME = "amazon"
    BASE_URL = "https://www.amazon.in"

    async def search_products(self, query: str, constraints: Dict[str, Any], max_results: int = 5) -> List[Dict[str, Any]]:
        products = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"{self.BASE_URL}/s?k={encoded}"
            app_logger.info(f"[Amazon] Fetching: {url}")

            soup = await self.fetch_page(url)
            if not soup:
                app_logger.warning("[Amazon] No page returned")
                return []

            cards = soup.select('[data-component-type="s-search-result"]')
            app_logger.info(f"[Amazon] Found {len(cards)} cards")

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
                    app_logger.warning(f"[Amazon] Card parse error: {e}")

        except Exception as e:
            app_logger.error(f"[Amazon] Search failed: {e}")

        app_logger.info(f"[Amazon] Returning {len(products)} products")
        return products

    def _parse_card(self, card) -> Optional[Dict[str, Any]]:
        # Extract full product title without getting tricked by brand logo aria-labels
        name = ""

        # 1. Standard Amazon search result title inside h2
        h2_span = card.select_one("h2 a span") or card.select_one("h2 span")
        if h2_span:
            name = h2_span.get_text(strip=True)

        # 2. Check title-recipe component
        if not name or len(name) < 5:
            recipe = card.select_one('[data-cy="title-recipe"] h2')
            if recipe:
                name = recipe.get_text(separator=" ", strip=True)

        # 3. Check img alt tag (on Amazon search cards, img alt is usually full title)
        if not name or len(name) < 5:
            img = card.select_one("img.s-image")
            if img:
                name = img.get("alt", "").strip()

        # 4. Check full h2 text
        if not name or len(name) < 5:
            h2 = card.select_one("h2")
            if h2:
                name = h2.get_text(separator=" ", strip=True)

        # 5. Fallback: aria-label on link if it's long enough (> 15 chars) to be a full product title
        if not name or len(name) < 5:
            link_with_label = card.select_one("a[aria-label]")
            if link_with_label:
                aria = link_with_label.get("aria-label", "").strip()
                if len(aria) > 15:
                    name = aria

        if not name or len(name) < 3:
            return None

        # Clean up any excess whitespace
        import re
        name = re.sub(r"\s+", " ", name).strip()

        # Truncate extremely long titles cleanly
        if len(name) > 200:
            name = name[:200].rsplit(" ", 1)[0]

        # Extract ASIN / Product ID
        asin = card.get("data-asin", "") or ""

        # URL
        link_el = card.select_one("h2 a") or card.select_one("a.a-link-normal")
        href = link_el.get("href", "") if link_el else ""
        product_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
        if not product_url:
            return None

        # Price
        price_el = card.select_one(".a-price .a-offscreen")
        price = self.parse_price(price_el.get_text() if price_el else "")

        # Original price
        orig_el = card.select_one(".a-price.a-text-price .a-offscreen")
        original_price = self.parse_price(orig_el.get_text() if orig_el else "")

        # Rating
        rating_el = card.select_one(".a-icon-alt")
        rating = self.parse_rating(rating_el.get_text() if rating_el else "")

        # Review count - use aria-label or span
        review_count = None
        for sel in ["[aria-label*='ratings']", "[aria-label*='reviews']", ".a-size-base.s-underline-text"]:
            el = card.select_one(sel)
            if el:
                aria = el.get("aria-label") or el.get_text()
                rc = self.parse_review_count(aria)
                if rc:
                    review_count = rc
                    break

        # Image
        img_el = card.select_one(".s-image")
        image_url = img_el.get("src", "") if img_el else ""

        # Delivery
        delivery_el = card.select_one('[data-cy="delivery-recipe"]')
        delivery_info = delivery_el.get_text(strip=True) if delivery_el else "Check on Amazon"

        brand = self._extract_brand(name)
        discount = self.calculate_discount(original_price, price)

        return {
            "product_id": asin or f"amazon_{hash(product_url) % 1000000}",
            "product_name": name,
            "title": name,
            "brand": brand,
            "platform": self.PLATFORM_NAME,
            "marketplace": self.PLATFORM_NAME,
            "price": price,
            "original_price": original_price,
            "discount": discount,
            "discount_percent": discount,
            "currency": "INR",
            "rating": rating,
            "review_count": review_count,
            "availability": True,
            "seller": "Amazon",
            "delivery_info": delivery_info,
            "delivery_date": delivery_info,
            "shipping_cost": 0.0,
            "image": image_url,
            "image_url": image_url,
            "url": product_url,
            "product_url": product_url,
            "specifications": {},
            "return_policy": "10 days return",
        }

    async def get_product_details(self, product_url: str) -> Dict[str, Any]:
        try:
            soup = await self.fetch_page(product_url)
            if not soup:
                return {}

            title_el = soup.select_one("#productTitle")
            title = title_el.get_text(strip=True) if title_el else ""

            price_el = soup.select_one(".a-price .a-offscreen")
            price = self.parse_price(price_el.get_text() if price_el else "")

            rating_el = soup.select_one("#acrPopover .a-icon-alt")
            rating = self.parse_rating(rating_el.get_text() if rating_el else "")

            review_el = soup.select_one("#acrCustomerReviewText")
            review_count = self.parse_review_count(review_el.get_text() if review_el else "")

            specs = {}
            for row in soup.select("#productDetails_techSpec_section_1 tr"):
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    specs[th.get_text(strip=True)] = td.get_text(strip=True)

            img_el = soup.select_one("#landingImage")
            image_url = img_el.get("src", "") if img_el else ""

            return {
                "product_name": title,
                "platform": self.PLATFORM_NAME,
                "price": price,
                "rating": rating,
                "review_count": review_count,
                "seller": "Amazon",
                "delivery_info": "Check on Amazon",
                "return_policy": "10 days return",
                "image_url": image_url,
                "product_url": product_url,
                "specifications": specs,
            }
        except Exception as e:
            app_logger.error(f"[Amazon] Detail error: {e}")
            return {}

    async def get_reviews(self, product_url: str, max_reviews: int = 20) -> List[str]:
        try:
            soup = await self.fetch_page(product_url)
            if not soup:
                return []
            reviews = []
            for el in soup.select(".review-text-content span")[:max_reviews]:
                text = el.get_text(strip=True)
                if text and len(text) > 20:
                    reviews.append(text)
            return reviews
        except Exception as e:
            app_logger.error(f"[Amazon] Reviews error: {e}")
            return []
