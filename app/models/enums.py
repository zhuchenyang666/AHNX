from enum import StrEnum, IntEnum


class CardBizType(StrEnum):
    NEW_CARD = "newcard"  # 新卡
    CHANGE_CARD = "changecard"  # 社保换卡


class CrdPrdSts(StrEnum):
    PENDING = "pending"  # 待制卡
    MAKING = "making"  # 制卡中
    FINISHED = "finished"  # 制卡完成


class HttpStatus(IntEnum):
    HTTP_200_OK = 200  # 请求已到达且处理完成（错误参数也返回200）
    HTTP_404_NOT_FOUND = 404  # 接口路径不存在
    HTTP_500_INTERNAL_SERVER_ERROR = 500  # 厂商服务端内部错误


class BizResCode(StrEnum):
    # BizResCode是唯一枚举来源 映射成对应的BizResText
    SUCCESS = "AAAAAAA"  # 交易成功
    PARAMETER_VALIDATOR_UNEXPECTED = "100001"  # 参数校验
    REQUEST_LOGIC_ERROR = "100002"  # Request violates business rules
    TIME_SPAN_ERROR = "100003"  # 查询时间跨度太大
    UNDEFINED_ERROR = "999999"  # 未定义错误

    @property
    def text(self) -> str:
        match self:
            case BizResCode.SUCCESS:
                return "交易成功"
            case BizResCode.PARAMETER_VALIDATOR_UNEXPECTED:
                return "Missing or invalid request parameters"
            case BizResCode.REQUEST_LOGIC_ERROR:
                return "Request violates business rules"
            case BizResCode.TIME_SPAN_ERROR:
                return "Date range must not exceed 90 days"
            case BizResCode.UNDEFINED_ERROR:
                return "Unknown error"
        # 防止以后新增错误码却忘记补充文案
        # raise ValueError(f"未配置业务响应文案：{self.value}")
