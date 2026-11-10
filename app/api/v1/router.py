from fastapi import APIRouter

from app.api.v1.endpoints import (
    card_progress_logistics_router,
    social_card_feedback_router
)

router = APIRouter()

router.include_router(card_progress_logistics_router)
router.include_router(social_card_feedback_router)
