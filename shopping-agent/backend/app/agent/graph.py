"""
LangGraph Shopping Agent — Production Graph.

Full pipeline:
  parse_query
  → search_products
  → deduplicate
  → calculate_total_cost
  → filter_products
  → analyze_reviews       (skipped if 0 products)
  → generate_recommendation
  → [END — frontend shows results + approval UI]

Cart/checkout is triggered separately via API after user approval.
Human-in-the-loop: user must click "Confirm Purchase" in the frontend.
Agent never auto-purchases.
"""
import json
import re
import time
from typing import Annotated, Any, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.llm_provider import get_llm
from app.agent.tools import (
    parse_shopping_query,
    search_products_tool,
    deduplicate_products,
    calculate_total_cost,
    compare_and_filter_products,
    fetch_reviews_tool,
    analyze_reviews_tool,
    generate_recommendation,
)
from app.core.logger import app_logger


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

class ShoppingAgentState(TypedDict):
    session_id: str
    search_id: Optional[int]
    user_id: Optional[int]
    raw_query: str
    original_query: Optional[str]

    parsed_constraints: Optional[str]   # JSON string
    requirements: Optional[dict]
    raw_products: Optional[str]         # JSON string — raw from scraper
    search_results: Optional[str]
    normalized_products: Optional[str]
    deduped_products: Optional[str]     # JSON string — after dedup
    product_groups: Optional[List[dict]]
    costed_products: Optional[str]      # JSON string — after total cost
    filtered_products: Optional[str]    # JSON string — after filter+rank
    shortlisted_products: Optional[str] # JSON string — top 5

    review_analyses: Optional[dict]     # product_name → analysis dict
    agent_explanation: Optional[str]
    top_pick_index: Optional[int]

    selected_product: Optional[dict]
    selected_marketplace: Optional[str]
    user_approval: Optional[bool]
    cart: Optional[dict]
    checkout: Optional[dict]
    order: Optional[dict]

    messages: Annotated[List[Any], lambda x, y: x + y]
    platforms_searched: List[str]
    marketplaces: Optional[List[str]]
    platform_status: dict               # {platform: "ok"|"unavailable"}

    current_step: str
    errors: List[str]

    awaiting_payment: bool
    status_callback: Optional[Any]      # async callable — not persisted


SYSTEM_PROMPT = """You are an AI shopping assistant for Indian e-commerce.
You help users find the best products across Amazon, Flipkart, and Snapdeal.

Rules:
- NEVER fabricate product data, prices, specs, or reviews
- ALWAYS use only data returned by tools
- NEVER handle payment credentials (CVV, OTP, PIN, passwords)
- ALWAYS stop and wait for explicit user approval before purchase
- Use deterministic tools for price/rating filtering — not LLM judgement
- Be concise, helpful, and honest about data availability"""


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────

async def node_parse_query(state: ShoppingAgentState) -> dict:
    """Node 1: Parse natural language query → structured constraints."""
    app_logger.info(f"[Graph] parse_query | {state['raw_query'][:60]}")
    await _emit(state, "thinking", "🔍 Understanding your request...")

    result = await parse_shopping_query.ainvoke({"query": state["raw_query"]})

    summary = _constraint_summary(result)
    await _emit(state, "status", f"✅ Query understood: {summary}")

    return {
        "parsed_constraints": result,
        "current_step": "search",
    }


async def node_search_products(state: ShoppingAgentState) -> dict:
    """Node 2: Search all active platforms in parallel."""
    app_logger.info("[Graph] search_products")

    constraints_json = state.get("parsed_constraints") or "{}"
    try:
        c = json.loads(constraints_json)
    except Exception:
        c = {}

    search_q = _build_query(state["raw_query"], c)
    await _emit(state, "status", f"🌐 Searching Amazon, Flipkart, Snapdeal for: {search_q[:50]}")

    result_json = await search_products_tool.ainvoke({
        "query": search_q,
        "constraints_json": constraints_json,
        "platforms": None,
    })

    try:
        result = json.loads(result_json)
        platforms = result.get("platforms_searched", [])
        failed   = result.get("platforms_failed", [])
        total    = result.get("total_count", 0)
        status   = result.get("platform_status", {})
    except Exception:
        platforms, failed, total, status = [], [], 0, {}

    # Emit per-platform status
    for p in platforms:
        await _emit(state, "platform_ok", f"✅ {p.capitalize()}: found results", platform=p)
    for p in failed:
        await _emit(state, "platform_fail", f"⚠️ {p.capitalize()}: temporarily unavailable", platform=p)

    await _emit(state, "status", f"Found {total} products across {len(platforms)} platforms")

    return {
        "raw_products": result_json,
        "platforms_searched": platforms,
        "platform_status": status,
        "current_step": "deduplicate",
    }


async def node_deduplicate(state: ShoppingAgentState) -> dict:
    """Node 3: Detect same product listed on multiple platforms."""
    app_logger.info("[Graph] deduplicate")
    await _emit(state, "thinking", "🔎 Matching same products across platforms...")

    raw = state.get("raw_products") or "{}"
    constraints = state.get("parsed_constraints") or "{}"

    result_json = await deduplicate_products.ainvoke({
        "products_json": raw,
        "constraints_json": constraints,
    })

    try:
        result = json.loads(result_json)
        groups = result.get("cross_platform_groups", 0)
        total  = result.get("total", 0)
    except Exception:
        groups, total = 0, 0

    if groups > 0:
        await _emit(state, "status", f"📊 Found {groups} products available on multiple platforms")
    else:
        await _emit(state, "status", f"📦 {total} unique products ready for comparison")

    return {
        "deduped_products": result_json,
        "current_step": "cost",
    }


async def node_calculate_cost(state: ShoppingAgentState) -> dict:
    """Node 4: Calculate total cost (price + shipping) for each product."""
    app_logger.info("[Graph] calculate_total_cost")
    await _emit(state, "thinking", "💰 Calculating total cost including shipping...")

    deduped = state.get("deduped_products") or state.get("raw_products") or "{}"

    result_json = await calculate_total_cost.ainvoke({"products_json": deduped})

    await _emit(state, "status", "💰 Total costs calculated")

    return {
        "costed_products": result_json,
        "current_step": "filter",
    }


async def node_filter_products(state: ShoppingAgentState) -> dict:
    """Node 5: Apply hard constraints + rank products."""
    app_logger.info("[Graph] filter_products")
    await _emit(state, "thinking", "⚖️ Filtering & ranking products...")

    costed = state.get("costed_products") or state.get("raw_products") or "{}"
    constraints = state.get("parsed_constraints") or "{}"

    result_json = await compare_and_filter_products.ainvoke({
        "products_json": costed,
        "constraints_json": constraints,
    })

    try:
        result = json.loads(result_json)
        shortlisted  = result.get("shortlisted_products", [])
        filtered_cnt = result.get("total_filtered", 0)
        rejected     = result.get("rejected_count", 0)
    except Exception:
        shortlisted, filtered_cnt, rejected = [], 0, 0

    msg = f"✅ {filtered_cnt} products match your requirements"
    if rejected > 0:
        msg += f" ({rejected} outside budget/rating)"
    await _emit(state, "status", msg)

    return {
        "filtered_products": result_json,
        "shortlisted_products": json.dumps(shortlisted),
        "current_step": "reviews",
    }


async def node_analyze_reviews(state: ShoppingAgentState) -> dict:
    """Node 6: Fetch + analyze reviews for top 3 shortlisted products."""
    app_logger.info("[Graph] analyze_reviews")

    try:
        shortlisted = json.loads(state.get("shortlisted_products") or "[]")
    except Exception:
        shortlisted = []

    if not shortlisted:
        return {"review_analyses": {}, "current_step": "recommend"}

    top3 = shortlisted[:3]
    analyses = {}

    for product in top3:
        name     = product.get("product_name", "Unknown")
        platform = product.get("platform", "")
        url      = product.get("product_url", "")
        if not url:
            continue

        await _emit(state, "status", f"⭐ Reading reviews for {name[:40]}...")

        try:
            reviews_json = await fetch_reviews_tool.ainvoke({
                "platform": platform,
                "product_url": url,
            })
            analysis_json = await analyze_reviews_tool.ainvoke({
                "product_name": name,
                "reviews_json": reviews_json,
            })
            analyses[name] = json.loads(analysis_json)
        except Exception as e:
            app_logger.warning(f"[Graph] Review analysis failed for {name}: {e}")
            analyses[name] = {
                "overall_sentiment": "unknown",
                "pros": [], "cons": [],
                "review_confidence": 0.0,
                "review_summary": "Review data unavailable.",
                "note": "fetch_failed",
            }

    return {"review_analyses": analyses, "current_step": "recommend"}


async def node_recommend(state: ShoppingAgentState) -> dict:
    """Node 7: Generate LLM recommendation + explanation."""
    app_logger.info("[Graph] generate_recommendation")
    await _emit(state, "thinking", "🤖 Preparing your personalized recommendation...")

    try:
        shortlisted = json.loads(state.get("shortlisted_products") or "[]")
    except Exception:
        shortlisted = []

    if not shortlisted:
        await _emit(state, "done", "No matching products found. Try broadening your search.")
        return {
            "agent_explanation": "No products matched your requirements. Try removing some filters.",
            "top_pick_index": None,
            "current_step": "done",
        }

    # Merge review analyses into shortlisted products
    analyses = state.get("review_analyses") or {}
    for p in shortlisted:
        name = p.get("product_name", "")
        if name in analyses:
            p["review_summary"] = analyses[name]

    try:
        result_json = await generate_recommendation.ainvoke({
            "user_query": state["raw_query"],
            "shortlisted_json": json.dumps({"shortlisted_products": shortlisted}),
            "constraints_json": state.get("parsed_constraints") or "{}",
        })
        result = json.loads(result_json)
        explanation = result.get("explanation", "")
        top_pick    = result.get("top_pick_index", 1)
    except Exception as e:
        app_logger.warning(f"[Graph] Recommendation generation failed ({e}), using fallback")
        top_prod = shortlisted[0] if shortlisted else {}
        top_name = top_prod.get("product_name") or "Selected Product"
        top_price = top_prod.get("total_cost") or top_prod.get("price") or 0
        top_platform = (top_prod.get("platform") or "online store").capitalize()
        explanation = (
            f"Based on price and customer ratings, we top-recommend **{top_name}** "
            f"from **{top_platform}** at ₹{top_price:,.0f}."
        )
        top_pick = 1

    await _emit(state, "done", explanation)

    return {
        "shortlisted_products": json.dumps(shortlisted),
        "agent_explanation": explanation,
        "top_pick_index": top_pick,
        "current_step": "human_approval",
        "awaiting_payment": True,
    }


async def node_human_approval(state: ShoppingAgentState) -> dict:
    """Node 8: Present recommendation & wait for human confirmation."""
    app_logger.info("[Graph] human_approval")
    await _emit(state, "status", "⏸️ Awaiting explicit user approval before purchase...")
    return {"current_step": "human_approval", "awaiting_payment": True}


async def node_add_to_cart(state: ShoppingAgentState) -> dict:
    """Node 9: Add selected product to cart on marketplace."""
    app_logger.info("[Graph] add_to_cart")
    await _emit(state, "thinking", "🛒 Preparing cart handoff for selected product...")
    product = state.get("selected_product") or {}
    platform = state.get("selected_marketplace") or product.get("platform", "amazon")
    url = product.get("product_url") or product.get("url", "")

    from app.agent.cart_handler import add_to_cart
    cart_res = await add_to_cart(platform, url)
    return {
        "cart": cart_res,
        "current_step": "checkout",
    }


async def node_checkout(state: ShoppingAgentState) -> dict:
    """Node 10: Prepare checkout summary & address verification."""
    app_logger.info("[Graph] checkout")
    await _emit(state, "status", "📋 Checkout summary prepared. Ready for user payment handoff.")
    cart = state.get("cart") or {}
    return {
        "checkout": {
            "status": "ready_for_payment",
            "cart_url": cart.get("cart_url"),
            "requires_user_action": True,
        },
        "current_step": "payment_handoff",
    }


async def node_payment_handoff(state: ShoppingAgentState) -> dict:
    """Node 11: Hand payment authorization to user. NEVER touches CVV/OTP/PIN."""
    app_logger.info("[Graph] payment_handoff")
    await _emit(state, "status", "🔒 Handing payment control to user. Complete payment securely on marketplace.")
    return {
        "current_step": "payment_handoff",
        "awaiting_payment": True,
    }


async def node_order_confirmation(state: ShoppingAgentState) -> dict:
    """Node 12: Record order confirmation once user completes payment."""
    app_logger.info("[Graph] order_confirmation")
    await _emit(state, "done", "✅ Order confirmed successfully!")
    return {
        "current_step": "done",
        "awaiting_payment": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Edge conditions
# ─────────────────────────────────────────────────────────────────────────────

def _after_filter(state: ShoppingAgentState) -> str:
    try:
        sl = json.loads(state.get("shortlisted_products") or "[]")
        return "analyze_reviews" if sl else "recommend"
    except Exception:
        return "recommend"


def _after_approval(state: ShoppingAgentState) -> str:
    approval = state.get("user_approval")
    if approval is True:
        return "add_to_cart"
    elif approval is False:
        return "parse_query"  # revise search
    return "human_approval"


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

def build_shopping_graph() -> StateGraph:
    g = StateGraph(ShoppingAgentState)

    g.add_node("parse_query",           node_parse_query)
    g.add_node("search_products",       node_search_products)
    g.add_node("deduplicate",           node_deduplicate)
    g.add_node("calculate_cost",        node_calculate_cost)
    g.add_node("filter_products",       node_filter_products)
    g.add_node("analyze_reviews",       node_analyze_reviews)
    g.add_node("generate_recommendation", node_recommend)
    g.add_node("human_approval",        node_human_approval)
    g.add_node("add_to_cart",           node_add_to_cart)
    g.add_node("checkout",              node_checkout)
    g.add_node("payment_handoff",       node_payment_handoff)
    g.add_node("order_confirmation",    node_order_confirmation)

    g.set_entry_point("parse_query")
    g.add_edge("parse_query",     "search_products")
    g.add_edge("search_products", "deduplicate")
    g.add_edge("deduplicate",     "calculate_cost")
    g.add_edge("calculate_cost",  "filter_products")
    g.add_conditional_edges(
        "filter_products",
        _after_filter,
        {"analyze_reviews": "analyze_reviews", "recommend": "generate_recommendation"},
    )
    g.add_edge("analyze_reviews",       "generate_recommendation")
    g.add_edge("generate_recommendation", "human_approval")
    g.add_conditional_edges(
        "human_approval",
        _after_approval,
        {
            "add_to_cart": "add_to_cart",
            "parse_query": "parse_query",
            "human_approval": END,
        },
    )
    g.add_edge("add_to_cart",        "checkout")
    g.add_edge("checkout",           "payment_handoff")
    g.add_edge("payment_handoff",    END)
    g.add_edge("order_confirmation", END)

    compiled = g.compile()
    app_logger.info("[Graph] Shopping agent compiled ✓")
    return compiled


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _emit(state: ShoppingAgentState, event_type: str, message: str, **extra):
    cb = state.get("status_callback")
    if cb and callable(cb):
        try:
            await cb({"type": event_type, "message": message, **extra})
        except Exception:
            pass
    app_logger.info(f"[Graph][{event_type.upper()}] {message}")


def _build_query(raw: str, c: dict) -> str:
    parts = []
    # 1. Main product / brand / model
    for key in ("brand", "product", "model", "variant"):
        v = c.get(key)
        if v:
            parts.append(str(v))
    # 2. Key specs like storage, RAM, size
    for key in ("storage", "ram", "size"):
        v = c.get(key)
        if v and str(v).lower() not in " ".join(parts).lower():
            parts.append(str(v))

    combined = " ".join(parts).lower() or raw.lower()

    # Anchor product type to avoid accessory results
    if any(m in raw.lower() for m in ["s24", "s23", "iphone", "phone", "mobile"]) and not any(k in combined for k in ["phone", "mobile", "smartphone"]):
        parts.append("5G phone")
    elif any(l in raw.lower() for l in ["laptop", "macbook", "notebook"]) and "laptop" not in combined:
        parts.append("laptop")
    elif "tv" in raw.lower() and "tv" not in combined:
        parts.append("TV")

    # Filter out intent noise words from search string sent to e-commerce scrapers
    noise_words = {
        "cheapest", "cheap", "best", "top", "lowest", "under", "below", "price",
        "coding", "gaming", "office", "student", "work", "for", "need", "find", "me", "buy"
    }

    query = " ".join(parts) if parts else raw
    clean_words = [w for w in query.split() if w.lower() not in noise_words]
    final_q = " ".join(clean_words) if clean_words else query
    return final_q


def _constraint_summary(constraints_json: str) -> str:
    try:
        c = json.loads(constraints_json)
        parts = []
        if c.get("brand"):     parts.append(c["brand"])
        if c.get("product"):   parts.append(c["product"])
        if c.get("model"):     parts.append(c["model"])
        if c.get("storage"):   parts.append(c["storage"])
        if c.get("max_price"): parts.append(f"under ₹{c['max_price']:,}")
        if c.get("min_rating"):parts.append(f"≥{c['min_rating']}★")
        return ", ".join(parts) if parts else "general search"
    except Exception:
        return "your requirements"


# Singleton
_graph = None

def get_shopping_graph():
    global _graph
    if _graph is None:
        _graph = build_shopping_graph()
    return _graph
