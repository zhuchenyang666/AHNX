"""制卡进度及物流信息查询接口。"""

from fastapi import APIRouter

from app.models import CardProgressLogisticsRequest, CardProgressLogisticsResponse
from app.services import CardProgressLogisticsQueryServiceImpl

router = APIRouter()
query_service = CardProgressLogisticsQueryServiceImpl()


@router.post(
    path="/ICCARD12001001",
    response_model=CardProgressLogisticsResponse,
    summary="制卡进度及物流信息查询",
)
async def query_card_progress_logistics(
        request: CardProgressLogisticsRequest,
) -> CardProgressLogisticsResponse:
    """执行通用 ESB 查询流程及制卡进度物流查询。"""
    return await query_service.execute(request)
