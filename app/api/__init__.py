"""HTTP API layer."""

from app.api.v1 import v1_router

__all__ = [
    "v1_router",
    # 未来可能添加v2_router,v2_router......
]
