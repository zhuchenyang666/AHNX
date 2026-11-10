"""Endpoint package reserved for future business interfaces."""
from app.api.v1.endpoints.card_progress_logistics import router as card_progress_logistics_router
from app.api.v1.endpoints.social_card_feedback import router as social_card_feedback_router

__all__ = [
    "card_progress_logistics_router",
    "social_card_feedback_router",
]
