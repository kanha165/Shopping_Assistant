from app.api.routes_auth import router as auth_router
from app.api.routes_search import router as search_router
from app.api.routes_products import router as products_router
from app.api.routes_agent import router as agent_router
from app.api.routes_orders import router as orders_router

__all__ = [
    "auth_router", "search_router", "products_router",
    "agent_router", "orders_router",
]
