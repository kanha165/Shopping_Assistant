"""
Agent Runner — public interface for FastAPI routes.
Supports both blocking run and real-time SSE streaming.
"""
import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator, Callable, Optional

from app.agent.graph import ShoppingAgentState, get_shopping_graph
from app.core.logger import app_logger


async def run_shopping_agent(
    query: str,
    session_id: Optional[str] = None,
    search_id: Optional[int] = None,
    user_id: Optional[int] = None,
    status_callback: Optional[Callable] = None,
) -> dict:
    """
    Run the full shopping agent pipeline (blocking).
    status_callback receives real-time events during execution.

    Returns: final result dict with all products + recommendation.
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    app_logger.info(f"[Runner] START session={session_id} query='{query[:60]}'")
    t0 = time.time()

    graph = get_shopping_graph()

    initial: ShoppingAgentState = {
        "session_id": session_id,
        "search_id": search_id,
        "user_id": user_id,
        "raw_query": query,
        "original_query": query,
        "requirements": None,
        "parsed_constraints": None,
        "raw_products": None,
        "search_results": None,
        "normalized_products": None,
        "deduped_products": None,
        "product_groups": [],
        "costed_products": None,
        "filtered_products": None,
        "shortlisted_products": None,
        "review_analyses": None,
        "agent_explanation": None,
        "top_pick_index": None,
        "selected_product": None,
        "selected_marketplace": None,
        "user_approval": None,
        "cart": None,
        "checkout": None,
        "order": None,
        "messages": [],
        "platforms_searched": [],
        "marketplaces": None,
        "platform_status": {},
        "current_step": "start",
        "errors": [],
        "awaiting_payment": False,
        "status_callback": status_callback,
    }

    try:
        final = await graph.ainvoke(initial)
        elapsed = round(time.time() - t0, 2)
        app_logger.info(f"[Runner] DONE in {elapsed}s session={session_id}")
        return _build_result(final, session_id, elapsed)

    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        app_logger.error(f"[Runner] FAILED in {elapsed}s: {e}")
        return {
            "session_id": session_id,
            "status": "failed",
            "error": str(e),
            "shortlisted_products": [],
            "all_products": [],
            "agent_explanation": "An error occurred. Please try again.",
            "platforms_searched": [],
            "platform_status": {},
            "elapsed_seconds": elapsed,
        }


async def run_shopping_agent_stream(
    query: str,
    session_id: Optional[str] = None,
    search_id: Optional[int] = None,
) -> AsyncGenerator[str, None]:
    """
    Run agent with real-time Server-Sent Events.
    Events are yielded AS THEY HAPPEN — not batched at the end.

    Usage: EventSource('/api/search/stream?query=...')
    Each line: data: <JSON>\n\n
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    # Queue for real-time event passing from callback to generator
    queue: asyncio.Queue = asyncio.Queue()
    SENTINEL = "__DONE__"

    async def on_status(event: dict):
        await queue.put(json.dumps(event))

    # Yield session start immediately
    yield f"data: {json.dumps({'type': 'start', 'message': 'Agent started', 'session_id': session_id})}\n\n"

    # Run agent in background task so we can yield events in real-time
    async def run_agent():
        try:
            result = await run_shopping_agent(
                query=query,
                session_id=session_id,
                search_id=search_id,
                status_callback=on_status,
            )
            await queue.put(json.dumps({"type": "result", "data": result}))
        except Exception as e:
            await queue.put(json.dumps({"type": "error", "message": str(e)}))
        finally:
            await queue.put(SENTINEL)

    task = asyncio.create_task(run_agent())

    # Yield events from queue as they arrive
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=120.0)
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Search timed out'})}\n\n"
            break

        if item == SENTINEL:
            break

        yield f"data: {item}\n\n"

    yield f"data: {json.dumps({'type': 'done', 'message': 'Search complete'})}\n\n"

    # Ensure task is cleaned up
    if not task.done():
        task.cancel()


def _build_result(state: ShoppingAgentState, session_id: str, elapsed: float) -> dict:
    try:
        shortlisted = json.loads(state.get("shortlisted_products") or "[]")
    except Exception:
        shortlisted = []

    try:
        fd = json.loads(state.get("filtered_products") or "{}")
        all_products = fd.get("filtered_products", [])
    except Exception:
        all_products = []

    try:
        constraints = json.loads(state.get("parsed_constraints") or "{}")
    except Exception:
        constraints = {}

    return {
        "session_id": session_id,
        "status": "completed",
        "raw_query": state.get("raw_query", ""),
        "parsed_constraints": constraints,
        "platforms_searched": state.get("platforms_searched", []),
        "platform_status": state.get("platform_status", {}),
        "total_products_found": len(all_products),
        "shortlisted_products": shortlisted,
        "all_products": all_products,
        "agent_explanation": state.get("agent_explanation", ""),
        "top_pick_index": state.get("top_pick_index"),
        "review_analyses": state.get("review_analyses", {}),
        "errors": state.get("errors", []),
        "elapsed_seconds": elapsed,
    }
