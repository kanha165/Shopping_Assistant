"""
LangGraph Agent Tools — complete production set.
LLM: planning, understanding, summarization, recommendation.
Deterministic: filtering, ranking, deduplication, price rules.
"""
import json
import math
import re
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from app.core.logger import app_logger
from app.core.config import settings


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — Query Parser
# ─────────────────────────────────────────────────────────────────────────────

def _rule_based_query_parser(query: str) -> dict:
    """Fallback rule-based parser when LLM API quota is exhausted or offline."""
    q = query.lower()
    constraints = {
        "keywords": [query],
        "category": None,
        "brand": None,
        "product": query,
        "model": None,
        "variant": None,
        "storage": None,
        "ram": None,
        "color": None,
        "size": None,
        "min_price": None,
        "max_price": None,
        "budget": None,
        "currency": "INR",
        "min_rating": None,
        "min_reviews": None,
        "condition": "new",
        "priority": "best_value"
    }

    # Extract price e.g. under 50k, under 60000
    price_match = re.search(r"(?:under|below|max|within|<=?)\s*(?:₹|rs\.?)?\s*(\d+(?:,\d+)*(?:\s*k|\s*lakh)?)", q)
    if price_match:
        val_str = price_match.group(1).replace(",", "").strip()
        if "k" in val_str:
            num = float(re.findall(r"[\d.]+", val_str)[0]) * 1000
        elif "lakh" in val_str:
            num = float(re.findall(r"[\d.]+", val_str)[0]) * 100000
        else:
            num = float(val_str)
        constraints["max_price"] = num
        constraints["budget"] = num

    if "cheapest" in q or "lowest" in q:
        constraints["priority"] = "lowest_price"
    elif "best" in q or "top" in q:
        constraints["priority"] = "best_rated"

    # Extract storage e.g. 256gb, 128gb
    storage_m = re.search(r"\b(\d+\s*(?:gb|tb))\b", q)
    if storage_m:
        constraints["storage"] = storage_m.group(1).upper().replace(" ", "")

    # Extract brand
    for b in ["Samsung", "Apple", "iPhone", "OnePlus", "Xiaomi", "Redmi", "Realme", "HP", "Dell", "Lenovo", "Asus", "Acer", "Sony", "LG"]:
        if b.lower() in q:
            constraints["brand"] = b
            break

    # Extract category
    if any(k in q for k in ["phone", "mobile", "s24", "s23", "iphone"]):
        constraints["category"] = "mobile"
    elif any(k in q for k in ["laptop", "macbook", "notebook"]):
        constraints["category"] = "laptop"
    elif "tv" in q:
        constraints["category"] = "tv"
    elif any(k in q for k in ["perfume", "fragrance", "cologne", "attar", "scent", "deo", "deodorant"]):
        constraints["category"] = "perfume"
    elif any(k in q for k in ["watch", "smartwatch", "analog", "wristwatch"]):
        constraints["category"] = "watch"
    elif any(k in q for k in ["shoe", "sneaker", "sandal", "slipper", "boot"]):
        constraints["category"] = "shoes"
    elif any(k in q for k in ["shirt", "tshirt", "t-shirt", "kurta", "jeans", "pant", "trouser"]):
        constraints["category"] = "clothing"

    return constraints


@tool
async def parse_shopping_query(query: str) -> str:
    """
    Parse a natural language shopping query into structured requirements.
    """
    try:
        from app.agent.llm_provider import get_llm
        llm = get_llm()

        prompt = f"""You are a shopping query parser for Indian e-commerce.
Extract ALL structured constraints from this query.

Query: "{query}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "category": "product category (TV/mobile/laptop/shoes/etc.)",
  "brand": "brand name or null",
  "product": "product name or null",
  "model": "model number/name or null",
  "variant": "specific variant or null",
  "storage": "storage if mentioned (256GB etc.) or null",
  "ram": "RAM if mentioned or null",
  "color": "color preference or null",
  "size": "size (55 inch / XL / etc.) or null",
  "min_price": null,
  "max_price": null,
  "budget": null,
  "currency": "INR",
  "min_rating": null,
  "min_reviews": null,
  "condition": "new/used/refurbished - default new",
  "delivery_days": null,
  "priority": "lowest_price/best_rated/best_value/fastest_delivery",
  "keywords": ["key search terms"],
  "specifications": {{}},
  "other": {{}}
}}

Rules:
- "under 50k" / "below 50000" → max_price: 50000, budget: 50000
- "cheapest" / "lowest price" → priority: "lowest_price"
- "best" / "top rated" → priority: "best_rated"
- "above 4 stars" → min_rating: 4.0
- "256GB" → storage: "256GB"
- Return ONLY the JSON object"""

        response = await llm.ainvoke(prompt)
        content = response.content.strip()

        if "```" in content:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if m:
                content = m.group(1).strip()

        parsed = json.loads(content)
        budget = parsed.get("budget") or parsed.get("max_price")
        parsed["budget"] = budget
        parsed["max_price"] = budget
        app_logger.info(f"[QueryParser] {parsed}")
        return json.dumps(parsed)
    except Exception as e:
        app_logger.warning(f"[QueryParser] LLM fallback triggered: {e}")
        fallback = _rule_based_query_parser(query)
        return json.dumps(fallback)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — Multi-platform Product Search
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def search_products_tool(
    query: str,
    constraints_json: str,
    platforms: Optional[str] = None,
) -> str:
    """
    Search products across Amazon, Flipkart, Snapdeal in parallel.
    Returns all raw results + per-platform status.

    Args:
        query: Optimised search string
        constraints_json: JSON from parse_shopping_query
        platforms: Optional comma-separated platform override
    Returns:
        JSON with all products + platform status.
    """
    from app.scrapers.scraper_manager import search_all_platforms

    try:
        constraints = json.loads(constraints_json) if constraints_json else {}
    except Exception:
        constraints = {}

    platform_list = [p.strip() for p in platforms.split(",")] if platforms else None

    app_logger.info(f"[SearchTool] query='{query}' platforms={platform_list}")

    results = await search_all_platforms(
        query=query,
        constraints=constraints,
        platforms=platform_list,
        max_per_platform=settings.MAX_PRODUCTS_PER_PLATFORM,
    )

    # Add platform failure info to each product for transparency
    for p in results["all_products"]:
        p.setdefault("shipping_cost", 0.0)
        p.setdefault("total_cost", p.get("price") or 0)

    return json.dumps({
        "total_count": results["total_count"],
        "platforms_searched": results["platforms_searched"],
        "platforms_failed": results["platforms_failed"],
        "platform_status": {
            **{p: "ok" for p in results["platforms_searched"]},
            **{p: "unavailable" for p in results["platforms_failed"]},
        },
        "products": results["all_products"],
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — Product Details
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def get_product_details_tool(platform: str, product_url: str) -> str:
    """
    Fetch full specs, seller info, delivery estimate for one product.

    Args:
        platform: 'amazon' | 'flipkart' | 'snapdeal'
        product_url: Full product page URL
    Returns:
        JSON with detailed product data.
    """
    from app.scrapers.scraper_manager import get_product_details
    app_logger.info(f"[DetailsTool] {platform} — {product_url[:60]}")
    details = await get_product_details(platform, product_url)
    return json.dumps(details)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — Review Fetcher
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def fetch_reviews_tool(platform: str, product_url: str) -> str:
    """
    Fetch raw customer review texts from a product page.

    Args:
        platform: platform name
        product_url: product page URL
    Returns:
        JSON with list of review strings.
    """
    from app.scrapers.scraper_manager import get_product_reviews
    reviews = await get_product_reviews(platform, product_url, max_reviews=25)
    return json.dumps({"reviews": reviews, "count": len(reviews)})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — Review Sentiment Analyzer
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def analyze_reviews_tool(product_name: str, reviews_json: str) -> str:
    """
    Analyze actual customer reviews using LLM.
    NEVER fabricates reviews. If none available, says so explicitly.

    Args:
        product_name: Product being analyzed
        reviews_json: JSON from fetch_reviews_tool
    Returns:
        JSON with pros, cons, sentiment, confidence.
    """
    from app.agent.llm_provider import get_llm

    try:
        data = json.loads(reviews_json)
        reviews = data.get("reviews", [])
    except Exception:
        reviews = []

    if not reviews:
        return json.dumps({
            "overall_sentiment": "unknown",
            "pros": [],
            "cons": [],
            "defects_mentioned": [],
            "value_for_money": "unknown",
            "delivery_feedback": None,
            "build_quality": None,
            "review_confidence": 0.0,
            "review_summary": "No reviews available to analyze.",
            "note": "reviews_unavailable",
        })

    llm = get_llm()
    review_text = "\n".join(f"- {r}" for r in reviews[:20])

    prompt = f"""Analyze ACTUAL customer reviews for "{product_name}".

Reviews:
{review_text}

Return ONLY valid JSON:
{{
  "overall_sentiment": "positive/negative/mixed",
  "pros": ["common positives customers mention"],
  "cons": ["common complaints"],
  "defects_mentioned": ["specific defects reported"],
  "value_for_money": "excellent/good/average/poor",
  "delivery_feedback": "delivery/packaging feedback or null",
  "build_quality": "build quality feedback or null",
  "review_confidence": 0.0,
  "review_summary": "2-sentence summary"
}}

review_confidence: 0-1 based on how many reviews and how consistent they are.
ONLY report what is in the reviews. Return ONLY the JSON."""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content.strip()
        if "```" in content:
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if m:
                content = m.group(1).strip()
        return json.dumps(json.loads(content))
    except Exception as e:
        app_logger.warning(f"[analyze_reviews_tool] LLM call failed ({e}), using rule-based review analysis fallback")
        text = " ".join(reviews).lower()
        pos_words = ["excellent", "good", "great", "awesome", "best", "stunning", "top", "worth", "love", "nice", "premium"]
        neg_words = ["bad", "poor", "worst", "expensive", "heating", "defective", "slow", "broken", "terrible", "fake"]
        pos_count = sum(text.count(w) for w in pos_words)
        neg_count = sum(text.count(w) for w in neg_words)

        sentiment = "positive" if pos_count > neg_count else ("negative" if neg_count > pos_count else "mixed")
        return json.dumps({
            "overall_sentiment": sentiment,
            "pros": [r for r in reviews if any(w in r.lower() for w in pos_words)][:3],
            "cons": [r for r in reviews if any(w in r.lower() for w in neg_words)][:3],
            "defects_mentioned": [],
            "value_for_money": "good" if "worth" in text or "value" in text else "average",
            "delivery_feedback": None,
            "build_quality": None,
            "review_confidence": 0.6 if len(reviews) > 0 else 0.0,
            "review_summary": f"Analyzed {len(reviews)} customer reviews. Overall sentiment: {sentiment}.",
            "note": "fallback_rule_based",
        })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 6 — Deduplication (Deterministic)
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def deduplicate_products(products_json: str, constraints_json: str) -> str:
    """
    Detect and group duplicate products across platforms (same product, different sellers).
    Uses title normalization + brand + storage/RAM matching.
    Groups them so user can compare prices for the exact same item.
    NO LLM — pure deterministic matching.

    Args:
        products_json: JSON list of products
        constraints_json: JSON constraints (used for spec matching)
    Returns:
        JSON with deduplicated list + product_groups for comparison.
    """
    try:
        data = json.loads(products_json)
        products = data.get("products", data) if isinstance(data, dict) else data
    except Exception:
        return json.dumps({"products": [], "product_groups": []})

    if not products:
        return json.dumps({"products": [], "product_groups": []})

    try:
        constraints = json.loads(constraints_json)
    except Exception:
        constraints = {}

    def normalize_title(title: str) -> str:
        """Strip noise, lowercase, remove punctuation for matching."""
        if not title:
            return ""
        t = title.lower()
        # Standardize unit spacing e.g. "256 GB" -> "256gb", "8 GB RAM" -> "8gb ram"
        t = re.sub(r"(\d+)\s+(gb|tb|mb)", r"\1\2", t)
        # Remove common marketplace noise
        noise = [
            "buy", "online", "at best price", "with", "official", "india",
            "(", ")", "[", "]", "|", "-", "–", "•", ",",
        ]
        for n in noise:
            t = t.replace(n, " ")
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def extract_key_specs(title: str) -> set:
        """Extract storage, RAM, color indicators from title."""
        specs = set()
        norm = normalize_title(title)
        # Storage: 128gb, 256gb, 512gb, 1tb, 2tb
        for m in re.findall(r"\d+(?:gb|tb)", norm):
            specs.add(m)
        # Model numbers e.g. s24, s23, iphone15, m34
        for m in re.findall(r"\b[a-z]?\d{2,4}[a-z]?\b", norm):
            if len(m) >= 2 and not m.endswith("gb") and not m.endswith("tb"):
                specs.add(m)
        return specs

    def similarity_score(a: str, b: str) -> float:
        """Word overlap similarity using normalized title."""
        norm_a = normalize_title(a)
        norm_b = normalize_title(b)
        words_a = set(norm_a.split())
        words_b = set(norm_b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    # Group products by similarity
    groups: List[List[int]] = []
    assigned = set()

    for i, prod in enumerate(products):
        if i in assigned:
            continue
        group = [i]
        assigned.add(i)
        title_i = prod.get("product_name", "")
        brand_i = (prod.get("brand") or "").lower()
        specs_i = extract_key_specs(title_i)

        for j, other in enumerate(products):
            if j <= i or j in assigned:
                continue
            title_j = other.get("product_name", "")
            brand_j = (other.get("brand") or "").lower()
            specs_j = extract_key_specs(title_j)

            # Same platform → never duplicate in our result set
            if prod.get("platform") == other.get("platform"):
                continue

            # Brand must match if both have brands
            if brand_i and brand_j and brand_i != brand_j:
                continue

            # Specs must match if both have extractable specs
            if specs_i and specs_j and not specs_i.intersection(specs_j):
                continue

            sim = similarity_score(title_i, title_j)
            spec_matches = len(specs_i.intersection(specs_j)) if (specs_i and specs_j) else 0
            if sim >= 0.40 or (brand_i and brand_i == brand_j and spec_matches >= 2):
                group.append(j)
                assigned.add(j)

        groups.append(group)

    # Build output — keep one representative per group (cheapest), tag others
    result_products = []
    product_groups = []

    for group in groups:
        group_products = [products[i] for i in group]

        # Sort group by total_cost ascending
        group_products.sort(key=lambda p: p.get("total_cost") or p.get("price") or 999999)

        # Tag cheapest in group
        group_products[0]["is_cheapest_for_product"] = True
        for p in group_products[1:]:
            p["is_cheapest_for_product"] = False

        # Build comparison group info
        if len(group_products) > 1:
            product_groups.append({
                "product_key": normalize_title(group_products[0].get("product_name", ""))[:60],
                "platforms": [p.get("platform") for p in group_products],
                "prices": {p.get("platform"): p.get("price") for p in group_products},
                "cheapest_platform": group_products[0].get("platform"),
                "cheapest_price": group_products[0].get("price"),
                "items": group_products,
            })

        result_products.extend(group_products)

    app_logger.info(
        f"[Deduplicate] {len(products)} → {len(result_products)} | "
        f"{len(product_groups)} cross-platform groups"
    )

    return json.dumps({
        "products": result_products,
        "product_groups": product_groups,
        "total": len(result_products),
        "cross_platform_groups": len(product_groups),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 7 — Total Cost Calculator (Deterministic)
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def calculate_total_cost(products_json: str) -> str:
    """
    Calculate total payable cost for each product: price + shipping.
    Does NOT add taxes that are already included in displayed price.
    Marks the product with lowest total cost.
    NO LLM — pure deterministic math.

    Args:
        products_json: JSON product list
    Returns:
        JSON with total_cost added to each product + cheapest flagged.
    """
    try:
        data = json.loads(products_json)
        products = data.get("products", data) if isinstance(data, dict) else data
    except Exception:
        return json.dumps({"products": []})

    PLATFORM_SHIPPING = {
        "amazon":   0.0,   # Free shipping on most orders
        "flipkart": 0.0,   # Free on most
        "snapdeal": 50.0,  # Sometimes charged
        "meesho":   0.0,
        "myntra":   0.0,
        "shopsy":   0.0,
    }

    for p in products:
        price = p.get("price") or 0.0
        platform = p.get("platform", "")
        # Use scraped shipping if present, else platform default
        shipping = p.get("shipping_cost") or PLATFORM_SHIPPING.get(platform, 0.0)
        total = price + shipping
        p["shipping_cost"] = shipping
        p["total_cost"] = round(total, 2)

    if products:
        products_with_price = [p for p in products if p.get("total_cost")]
        if products_with_price:
            min_cost = min(p["total_cost"] for p in products_with_price)
            for p in products:
                p["is_lowest_price"] = (
                    bool(p.get("total_cost")) and p["total_cost"] == min_cost
                )

    return json.dumps({"products": products})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 8 — Filter + Rank (Deterministic)
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def compare_and_filter_products(
    products_json: str,
    constraints_json: str,
) -> str:
    """
    Apply hard constraint filtering then rank by composite score.
    Hard rules (NO LLM):
      - price > max_price → reject
      - rating < min_rating → reject
      - review_count < min_reviews → reject
    Ranking formula:
      score = rating(40%) + review_volume(30%) + value/discount(30%)
    If priority=lowest_price, sort by total_cost first.

    Args:
        products_json: JSON product list
        constraints_json: JSON constraints
    Returns:
        JSON with filtered + ranked products + shortlist.
    """
    try:
        data = json.loads(products_json)
        products = data.get("products", data) if isinstance(data, dict) else data
    except Exception:
        return json.dumps({"filtered_products": [], "shortlisted_products": [], "rejected_count": 0})

    try:
        constraints = json.loads(constraints_json)
    except Exception:
        constraints = {}

    max_price   = constraints.get("max_price") or constraints.get("budget")
    min_price   = constraints.get("min_price")
    min_rating  = constraints.get("min_rating")
    min_reviews = constraints.get("min_reviews")
    storage_req = constraints.get("storage")
    ram_req     = constraints.get("ram")
    priority    = constraints.get("priority", "best_value")

    # Target category detection to prevent recommending cases/books/stickers for device queries
    raw_target = " ".join([
        str(constraints.get("product") or ""),
        str(constraints.get("category") or ""),
        str(constraints.get("brand") or ""),
        str(constraints.get("keywords") or ""),
    ]).lower()

    is_phone_query  = any(k in raw_target for k in ["phone", "mobile", "samsung", "iphone", "galaxy", "redmi", "realme", "oneplus", "vivo", "oppo", "s24", "s23"])
    is_laptop_query = any(k in raw_target for k in ["laptop", "macbook", "notebook"])
    is_tv_query     = any(k in raw_target for k in ["tv", "television"])
    is_perfume_query = any(k in raw_target for k in ["perfume", "fragrance", "cologne", "deodorant", "deo", "eau de", "attar", "scent"])
    is_watch_query  = any(k in raw_target for k in ["watch", "smartwatch", "analog", "digital watch", "wristwatch"])
    is_shoe_query   = any(k in raw_target for k in ["shoe", "sneaker", "sandal", "slipper", "boot", "footwear"])
    is_shirt_query  = any(k in raw_target for k in ["shirt", "tshirt", "t-shirt", "kurta", "top", "jeans", "trouser", "pant"])

    accessory_words = [
        "case", "cover", "back cover", "tempered glass", "screen guard", "protector",
        "pouch", "skin", "sticker", "stickers", "book", "guide", "toy", "kit", "mouse pad"
    ]

    # Non-perfume words that should be rejected for perfume queries
    perfume_reject_words = [
        "idol", "murti", "statue", "pendant", "locket", "necklace", "chain",
        "dvd", "blu-ray", "movie", "film", "book", "poster", "frame", "wallet",
        "keychain", "bracelet", "ring", "earring", "figurine", "showpiece",
        "incense", "agarbatti", "candle", "diffuser", "puja", "pooja",
    ]

    filtered, rejected = [], 0

    for p in products:
        price   = p.get("price")
        rating  = p.get("rating")
        reviews = p.get("review_count")
        title_lower = (p.get("product_name") or p.get("title") or "").lower()

        if max_price and price and price > max_price:
            rejected += 1; continue
        if min_price and price and price < min_price:
            rejected += 1; continue
        if min_rating and rating and rating < min_rating:
            rejected += 1; continue
        if min_reviews and reviews and reviews < min_reviews:
            rejected += 1; continue

        # Filter out accessories when user is searching for a main device
        if is_phone_query:
            if any(acc in title_lower for acc in accessory_words) and not any(acc in raw_target for acc in accessory_words):
                rejected += 1; continue
            if price and price < 3000:
                rejected += 1; continue

        if is_laptop_query:
            if any(acc in title_lower for acc in accessory_words) and not any(acc in raw_target for acc in accessory_words):
                rejected += 1; continue
            if price and price < 12000:
                rejected += 1; continue

        if is_tv_query:
            if any(acc in title_lower for acc in ["mount", "bracket", "remote", "cable", "cover"]) and not any(acc in raw_target for acc in ["mount", "remote"]):
                rejected += 1; continue
            if price and price < 5000:
                rejected += 1; continue

        # Perfume query — reject idols, pendants, movies, books etc.
        if is_perfume_query:
            if any(w in title_lower for w in perfume_reject_words):
                rejected += 1; continue
            # Must contain at least one perfume-related word in title
            perfume_title_words = ["perfume", "fragrance", "cologne", "eau de", "edp", "edt",
                                   "deodorant", "deo", "attar", "scent", "spray", "body mist"]
            if not any(w in title_lower for w in perfume_title_words):
                rejected += 1; continue

        # Watch query — reject watch straps, cases, covers
        if is_watch_query:
            watch_reject = ["strap", "band", "cover", "case", "charger", "cable",
                           "screen guard", "protector", "book", "poster"]
            if any(w in title_lower for w in watch_reject):
                rejected += 1; continue

        # Shoe query — reject shoe racks, polish, laces, cleaners
        if is_shoe_query:
            shoe_reject = ["rack", "polish", "cleaner", "lace", "insole", "organizer", "box"]
            if any(w in title_lower for w in shoe_reject):
                rejected += 1; continue

        # Shirt query — reject hangers, covers, irons, detergent
        if is_shirt_query:
            shirt_reject = ["hanger", "iron", "detergent", "cover", "organizer", "bag"]
            if any(w in title_lower for w in shirt_reject):
                rejected += 1; continue

        # Strict Storage Variant Check (e.g. 128GB requested -> reject 64GB / 256GB)
        if storage_req:
            req_clean = re.sub(r"\s+", "", str(storage_req).lower())
            found_storages = [s.replace(" ", "") for s in re.findall(r"\d+\s*(?:gb|tb)", title_lower)]
            if found_storages and req_clean not in found_storages:
                rejected += 1; continue

        # Strict RAM Check
        if ram_req:
            req_ram = re.sub(r"\s+", "", str(ram_req).lower())
            found_rams = [r.replace(" ", "") for r in re.findall(r"\d+\s*gb\s*ram", title_lower)]
            if found_rams and req_ram not in found_rams:
                rejected += 1; continue

        filtered.append(p)

    def rank_score(p: dict) -> float:
        score = 0.0
        price    = p.get("total_cost") or p.get("price") or 0
        rating   = p.get("rating") or 0
        reviews  = p.get("review_count") or 0
        original = p.get("original_price") or price

        score += (rating / 5.0) * 40
        if reviews > 0:
            score += min(math.log10(reviews + 1) / 5.0, 1.0) * 30
        if original > 0 and price > 0 and original > price:
            score += ((original - price) / original) * 30

        return round(score, 2)

    for p in filtered:
        p["rank_score"] = rank_score(p)

    if priority == "lowest_price":
        filtered.sort(key=lambda x: x.get("total_cost") or x.get("price") or 999999)
    elif priority == "best_rated":
        filtered.sort(key=lambda x: x.get("rating") or 0, reverse=True)
    elif priority == "fastest_delivery":
        # Delivery days not parsed yet — fall back to rank_score
        filtered.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
    else:
        filtered.sort(key=lambda x: x.get("rank_score", 0), reverse=True)

    shortlisted = []
    for i, p in enumerate(filtered):
        p["is_shortlisted"] = i < 15
        if i < 15:
            shortlisted.append(p)

    app_logger.info(
        f"[Filter] in={len(products)} filtered={len(filtered)} "
        f"rejected={rejected} shortlisted={len(shortlisted)}"
    )

    return json.dumps({
        "filtered_products": filtered,
        "shortlisted_products": shortlisted,
        "total_input": len(products),
        "total_filtered": len(filtered),
        "rejected_count": rejected,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Tool 9 — Recommendation Generator
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def generate_recommendation(
    user_query: str,
    shortlisted_json: str,
    constraints_json: str,
) -> str:
    """
    Generate human-friendly recommendation explanation using LLM.
    Only uses actual data — never fabricates specs or prices.

    Args:
        user_query: Original user query
        shortlisted_json: Top products
        constraints_json: Parsed constraints
    Returns:
        JSON with explanation + top pick.
    """
    from app.agent.llm_provider import get_llm

    try:
        data = json.loads(shortlisted_json)
        products = data.get("shortlisted_products", data) if isinstance(data, dict) else data
    except Exception:
        products = []

    if not products:
        return json.dumps({
            "explanation": "No matching products found for your query. Try broadening your search.",
            "top_pick_index": None,
        })

    llm = get_llm()

    summaries = []
    for i, p in enumerate(products[:5], 1):
        total = p.get("total_cost") or p.get("price")
        line = (
            f"{i}. {p.get('product_name','?')[:70]} | "
            f"Platform: {p.get('platform','?')} | "
            f"Price: ₹{p.get('price','N/A')} | "
            f"Total (incl. shipping): ₹{total or 'N/A'} | "
            f"Rating: {p.get('rating','N/A')}/5 | "
            f"Reviews: {p.get('review_count','N/A')} | "
            f"Delivery: {p.get('delivery_info','N/A')}"
        )
        summaries.append(line)

    try:
        constraints = json.loads(constraints_json)
    except Exception:
        constraints = {}

    priority = constraints.get("priority", "best_value")

    prompt = f"""You are an AI shopping assistant helping an Indian customer.

User searched for: "{user_query}"
Priority: {priority}

Top products found:
{chr(10).join(summaries)}

Write a concise recommendation (3-5 sentences):
1. Which product is the best match and WHY (based on data above only)
2. Key trade-offs between options
3. Which platform offers the best deal for this product

Rules:
- Use ONLY the data above — do NOT add fake specs, prices, or features
- Be conversational and helpful
- End with a clear recommendation

Also return top_pick_index (1-based number of the best pick from the list above)."""

    try:
        response = await llm.ainvoke(prompt)
        text = response.content.strip()

        # Try to extract top_pick_index from response
        top_pick = 1
        m = re.search(r"top_pick_index[:\s]+(\d)", text, re.IGNORECASE)
        if m:
            top_pick = int(m.group(1))
            text = re.sub(r"top_pick_index[:\s]+\d", "", text).strip()

        return json.dumps({"explanation": text, "top_pick_index": top_pick})
    except Exception as e:
        app_logger.warning(f"[generate_recommendation] LLM call failed ({e}), using rule-based recommendation fallback")
        top_prod = products[0]
        top_name = top_prod.get("product_name") or top_prod.get("title") or "Item"
        top_price = top_prod.get("total_cost") or top_prod.get("price") or 0
        top_platform = (top_prod.get("platform") or "online store").capitalize()
        top_rating = top_prod.get("rating") or "N/A"

        fallback_text = (
            f"Based on price and customer rating analysis, we top-recommend **{top_name}** "
            f"from **{top_platform}** at ₹{top_price:,.0f} (Rating: {top_rating}/5). "
            f"It offers the best value among all verified options found across marketplaces."
        )
        return json.dumps({"explanation": fallback_text, "top_pick_index": 1})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 10 — Cart Handoff
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def add_to_cart_tool(platform: str, product_url: str) -> str:
    """
    Prepare cart handoff — returns the cart URL for the user to open.
    Agent STOPS here. Human must complete payment.
    NEVER handles CVV, OTP, passwords, or payment credentials.

    Args:
        platform: 'amazon' | 'flipkart' | 'snapdeal'
        product_url: Full product URL
    Returns:
        JSON with cart_url and instructions.
    """
    from app.agent.cart_handler import add_to_cart
    app_logger.info(f"[CartTool] {platform} — {product_url[:60]}")
    result = await add_to_cart(platform, product_url)
    return json.dumps(result)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 11 — Specification Filter (Deterministic)
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def filter_by_specifications(products_json: str, specs_json: str) -> str:
    """
    Filter products by required technical specifications.
    Checks both specifications dict and product name.
    NO LLM — pure rule-based filtering.

    Args:
        products_json: JSON product list
        specs_json: Required specs dict e.g. {"storage": "256GB", "resolution": "4K"}
    Returns:
        JSON with matching products.
    """
    try:
        data = json.loads(products_json)
        products = data.get("products", data.get("filtered_products", data)) if isinstance(data, dict) else data
    except Exception:
        return json.dumps({"products": []})

    try:
        required = json.loads(specs_json)
    except Exception:
        return json.dumps({"products": products})

    if not required:
        return json.dumps({"products": products})

    matched = []
    for product in products:
        specs  = product.get("specifications") or {}
        name   = (product.get("product_name") or "").lower()
        match  = True

        for key, val in required.items():
            val_lower = str(val).lower()
            key_lower = key.lower()
            found = False

            for k, v in specs.items():
                if key_lower in k.lower() and val_lower in str(v).lower():
                    found = True
                    break

            if not found and val_lower in name:
                found = True

            if not found:
                match = False
                break

        if match:
            matched.append(product)

    app_logger.info(f"[SpecFilter] {len(products)} → {len(matched)} matched")
    return json.dumps({"products": matched, "count": len(matched)})


# ─────────────────────────────────────────────────────────────────────────────
# Tools registry
# ─────────────────────────────────────────────────────────────────────────────

ALL_TOOLS = [
    parse_shopping_query,       # 0
    search_products_tool,       # 1
    get_product_details_tool,   # 2
    fetch_reviews_tool,         # 3
    analyze_reviews_tool,       # 4
    deduplicate_products,       # 5
    calculate_total_cost,       # 6
    compare_and_filter_products,# 7
    generate_recommendation,    # 8
    add_to_cart_tool,           # 9
    filter_by_specifications,   # 10
]
