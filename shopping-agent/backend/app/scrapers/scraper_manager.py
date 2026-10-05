"""
Scraper Manager - orchestrates multiple platform scrapers in parallel.
This is the single entry point the LangGraph agent calls.
"""
import asyncio
from typing import List, Dict, Any, Optional
from app.scrapers.amazon_scraper import AmazonScraper
from app.scrapers.flipkart_scraper import FlipkartScraper
from app.scrapers.meesho_scraper import MeeshoScraper
from app.scrapers.myntra_scraper import MyntraScraper
from app.scrapers.shopsy_scraper import ShopsyScraper
from app.scrapers.snapdeal_scraper import SnapdealScraper
from app.core.config import settings
from app.core.logger import app_logger

# Registry of all available scrapers
SCRAPER_REGISTRY = {
    "amazon": AmazonScraper,
    "flipkart": FlipkartScraper,
    "meesho": MeeshoScraper,
    "myntra": MyntraScraper,
    "shopsy": ShopsyScraper,
    "snapdeal": SnapdealScraper,
}

# Default platforms to search
DEFAULT_PLATFORMS = ["amazon", "flipkart", "snapdeal", "meesho", "myntra"]

# Fashion queries
FASHION_PLATFORMS = ["amazon", "flipkart", "snapdeal", "myntra", "meesho", "shopsy"]

# Electronics
ELECTRONICS_PLATFORMS = ["amazon", "flipkart", "snapdeal"]


def get_platforms_for_category(category: Optional[str], requested: Optional[List[str]] = None) -> List[str]:
    """Pick the right set of platforms based on product category."""
    if requested:
        # User specified platforms - only use valid ones
        return [p for p in requested if p in SCRAPER_REGISTRY]

    if not category:
        return DEFAULT_PLATFORMS

    category_lower = category.lower()
    fashion_keywords = ["shirt", "pant", "dress", "shoe", "kurta", "saree", "jeans",
                        "jacket", "clothing", "fashion", "apparel", "wear", "top", "kurti", "perfume", "fragrance"]
    electronics_keywords = ["tv", "laptop", "phone", "mobile", "camera", "refrigerator",
                            "ac", "washing machine", "speaker", "headphone", "tablet", "monitor"]

    if any(kw in category_lower for kw in fashion_keywords):
        return FASHION_PLATFORMS
    elif any(kw in category_lower for kw in electronics_keywords):
        return ["amazon", "flipkart", "snapdeal", "meesho"]
    else:
        return DEFAULT_PLATFORMS


async def search_single_platform(
    platform: str,
    query: str,
    constraints: Dict[str, Any],
    max_results: int,
) -> Dict[str, Any]:
    """Run search on one platform and return results with platform metadata."""
    scraper_class = SCRAPER_REGISTRY.get(platform)
    if not scraper_class:
        return {
            "platform": platform,
            "marketplace": platform,
            "status": "unavailable",
            "reason": "unknown_platform",
            "products": [],
            "error": "Unknown platform",
        }

    scraper = scraper_class()
    try:
        app_logger.info(f"[ScraperManager] Starting {platform} search for: {query}")
        products = await scraper.search_products(query, constraints, max_results)
        if not products and platform in ("meesho", "myntra"):
            reason = "bot_protection" if platform == "meesho" else "javascript_rendering_required"
            return {
                "platform": platform,
                "marketplace": platform,
                "status": "unavailable",
                "reason": reason,
                "products": [],
                "error": reason,
            }

        app_logger.info(f"[ScraperManager] {platform} returned {len(products)} products")
        return {
            "platform": platform,
            "marketplace": platform,
            "status": "ok",
            "products": products,
            "error": None,
        }
    except Exception as e:
        app_logger.error(f"[ScraperManager] {platform} scraper error: {e}")
        reason = "bot_protection" if "403" in str(e) or platform == "meesho" else str(e)
        return {
            "platform": platform,
            "marketplace": platform,
            "status": "unavailable",
            "reason": reason,
            "products": [],
            "error": str(e),
        }


async def search_all_platforms(
    query: str,
    constraints: Dict[str, Any],
    platforms: Optional[List[str]] = None,
    max_per_platform: int = None,
) -> Dict[str, Any]:
    """
    Search multiple platforms concurrently and aggregate results.
    """
    max_per_platform = max_per_platform or settings.MAX_PRODUCTS_PER_PLATFORM
    category = constraints.get("category")
    target_platforms = get_platforms_for_category(category, platforms)

    app_logger.info(f"[ScraperManager] Searching {len(target_platforms)} platforms: {target_platforms}")
    app_logger.info(f"[ScraperManager] Query: '{query}' | Constraints: {constraints}")

    # Run all platform searches concurrently
    tasks = [
        search_single_platform(platform, query, constraints, max_per_platform)
        for platform in target_platforms
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate
    all_products = []
    by_platform = {}
    platforms_searched = []
    platforms_failed = []
    platform_status = {}

    for platform_name, result in zip(target_platforms, results):
        # Handle unexpected exceptions from gather (return_exceptions=True)
        if isinstance(result, Exception):
            app_logger.error(f"[ScraperManager] {platform_name} raised exception: {result}")
            platforms_failed.append(platform_name)
            platform_status[platform_name] = {
                "marketplace": platform_name,
                "status": "unavailable",
                "reason": str(result),
            }
            continue

        platform = result["platform"]
        if result["error"] or result["status"] == "unavailable":
            platforms_failed.append(platform)
            platform_status[platform] = {
                "marketplace": platform,
                "status": "unavailable",
                "reason": result.get("reason") or result.get("error") or "unavailable",
            }
            app_logger.warning(f"[ScraperManager] {platform} failed: {result.get('reason') or result['error']}")
        else:
            platforms_searched.append(platform)
            platform_status[platform] = {
                "marketplace": platform,
                "status": "ok",
                "count": len(result["products"]),
            }
            by_platform[platform] = result["products"]
            all_products.extend(result["products"])

    app_logger.info(
        f"[ScraperManager] Done. Total products: {len(all_products)} | "
        f"Success: {platforms_searched} | Failed: {platforms_failed}"
    )

    return {
        "all_products": all_products,
        "by_platform": by_platform,
        "platforms_searched": platforms_searched,
        "platforms_failed": platforms_failed,
        "platform_status": platform_status,
        "total_count": len(all_products),
    }


async def get_product_details(platform: str, product_url: str) -> Dict[str, Any]:
    """Get detailed info for a single product from its platform scraper."""
    scraper_class = SCRAPER_REGISTRY.get(platform)
    if not scraper_class:
        return {}
    scraper = scraper_class()
    try:
        return await scraper.get_product_details(product_url)
    except Exception as e:
        app_logger.error(f"[ScraperManager] Detail fetch error [{platform}]: {e}")
        return {}


async def get_product_reviews(platform: str, product_url: str, max_reviews: int = 20) -> List[str]:
    """Fetch reviews for a product from its platform scraper."""
    scraper_class = SCRAPER_REGISTRY.get(platform)
    if not scraper_class:
        return []
    scraper = scraper_class()
    try:
        return await scraper.get_reviews(product_url, max_reviews)
    except Exception as e:
        app_logger.error(f"[ScraperManager] Review fetch error [{platform}]: {e}")
        return []
