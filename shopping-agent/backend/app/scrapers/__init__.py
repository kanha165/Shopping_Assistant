from app.scrapers.scraper_manager import (
    search_all_platforms,
    get_product_details,
    get_product_reviews,
    SCRAPER_REGISTRY,
)

__all__ = [
    "search_all_platforms",
    "get_product_details",
    "get_product_reviews",
    "SCRAPER_REGISTRY",
]
