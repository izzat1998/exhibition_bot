"""Import all routers and add them to routers_list."""

from .admin import admin_router
from .lead import lead_router
from .user import user_router

routers_list = [
    admin_router,
    user_router,
    lead_router,

]

__all__ = [
    "routers_list",
]
