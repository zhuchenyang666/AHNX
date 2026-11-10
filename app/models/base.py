"""报文模型基础能力。"""

from typing import Self, Any
from pydantic import BaseModel, ConfigDict


class MessageModel(BaseModel):
    """统一配置 JSON 解析、序列化及未知字段处理。"""

    model_config = ConfigDict(
        extra="forbid",  # 禁止多余参数 不过我觉得应该允许多余参数
        validate_by_alias=True,  # JSON 输入允许使用报文字段别名
        validate_by_name=True,  # Python 输入同时允许使用模型属性名
        serialize_by_alias=True,  # Python 对象序列化时默认使用报文字段别名
        str_strip_whitespace=True,
    )

    @classmethod
    def from_json(cls, data: str | bytes | bytearray) -> Self:
        """从 JSON 字符串或字节反序列化Python对象。"""
        return cls.model_validate_json(data)

    # 值为 None 的字段会保留
    def to_json(self, *, exclude_none: bool = False) -> str:
        """按字段别名将完整报文序列化为 JSON 字符串。"""
        return self.model_dump_json(exclude_none=exclude_none)

    # 来自字典
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        # Mapping[str, Any]只读不可修改
        # dict[str,Any]可读可修改
        return cls.model_validate(data)

    # 转化为字典
    def to_dict(self, *, exclude_none: bool = False) -> dict[str, Any]:
        # mode="json"它会把枚举、日期等类型转换成适合 JSON 响应的值
        return self.model_dump(exclude_none=exclude_none, mode="json", by_alias=True)
