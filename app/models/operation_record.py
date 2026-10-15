"""会话操作记录。"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OperationRecord:
    operation: str
    description: str
    affected: int = 0
    columns: str = ""
    success: bool = True
    time: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self):
        return {"操作时间": self.time, "操作类型": self.operation, "操作描述": self.description,
                "影响记录数": self.affected, "影响字段": self.columns, "是否成功": "成功" if self.success else "失败"}
