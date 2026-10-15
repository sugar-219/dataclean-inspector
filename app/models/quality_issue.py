"""检测问题与结果的数据结构，与 GUI 无关。"""
from dataclasses import dataclass, field


@dataclass
class QualityIssue:
    kind: str
    category: str
    column: str
    rows: list[int]
    description: str
    severity: str
    suggestion: str
    details: dict = field(default_factory=dict)

    @property
    def count(self):
        return len(self.rows)


@dataclass
class DetectionResult:
    issues: list
    fields: object
    metrics: dict
    score: dict
    detected_at: str

    @property
    def issue_count(self):
        return len(self.issues)
