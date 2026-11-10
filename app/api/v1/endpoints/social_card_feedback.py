from fastapi import APIRouter

from app.models import (
    SocialCardFeedbackRequest,
    SocialCardFeedbackResponse
)
from app.services import SocialCardFeedBackQueryServiceImpl

router = APIRouter()
query_service = SocialCardFeedBackQueryServiceImpl()


@router.post(
    path="/ICCARD12001002",
    response_model=SocialCardFeedbackResponse,
    summary="社保卡制卡回盘文件查询"
)
async def query_social_card_feedback(request: SocialCardFeedbackRequest) -> SocialCardFeedbackResponse:
    """执行通用 ESB 查询流程及制卡进度物流查询。"""
    return await query_service.execute(request)
