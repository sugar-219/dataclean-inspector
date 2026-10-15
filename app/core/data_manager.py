"""管理数据状态、检测缓存、清洗事务和会话记录，不依赖 Qt。"""
import pandas as pd
from app.core.quality_detector import detect_quality
from app.core.cleaner import clean_data
from app.core.undo_manager import UndoManager
from app.core.analyzer import analyze
from app.models.operation_record import OperationRecord


class DataManager:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})
        self.frame = pd.DataFrame()
        self.original = None
        self.metadata = {}
        self.result = self.baseline = None
        self.analysis = {}
        self.undo = UndoManager(self.settings.get("undo_limit", 20))
        self.records = []
        self.dirty = False

    def load(self, frame, metadata):
        result = detect_quality(frame, self.settings)
        analysis = analyze(frame)
        self.frame = frame
        self.original = frame.copy(deep=True)
        self.metadata = metadata
        self.result = self.baseline = result
        self.analysis = analysis
        self.undo.clear()
        self.dirty = False
        self.record("导入文件", f"读取 {metadata.get('name', '')}，工作表：{metadata.get('sheet') or '默认'}", len(frame))

    def detect(self, settings=None):
        config = dict(settings if settings is not None else self.settings)
        result = detect_quality(self.frame, config)
        baseline = detect_quality(self.original, config) if self.original is not None else result
        self.result, self.baseline, self.settings = result, baseline, config
        self.undo.set_limit(config.get("undo_limit", 20))
        self.record("质量检测", f"完成 {result.issue_count} 项问题检查；评分 {result.score['score']}")
        return result

    def apply(self, operation, columns=None, **params):
        change = clean_data(self.frame, operation, columns, **params)
        if self.frame.equals(change.frame):
            self.record(operation, change.description + "；没有数据变化", 0, change.columns)
            return change
        # 检测或统计失败时不提交状态，原数据及撤销栈保持不变。
        result = detect_quality(change.frame, self.settings)
        analysis = analyze(change.frame)
        self.undo.push((self.frame, self.dirty))
        self.frame, self.result, self.analysis = change.frame, result, analysis
        self.dirty = True
        self.record(operation, change.description, change.affected, change.columns)
        return change

    def undo_last(self):
        frame, dirty = self.undo.peek()
        # 重新计算成功后才移除快照，失败时仍可重试撤销。
        result = detect_quality(frame, self.settings)
        analysis = analyze(frame)
        self.undo.pop()
        self.frame, self.result, self.analysis, self.dirty = frame, result, analysis, dirty
        self.record("撤销", "恢复上一步清洗之前的数据状态", len(frame))

    def record(self, operation, description, affected=0, columns=None, success=True):
        self.records.append(OperationRecord(operation, description, affected, "、".join(map(str, columns or [])), success))

    def comparison(self):
        if self.baseline is None or self.result is None:
            return pd.DataFrame()
        fields = [
            ("数据行数", "rows"),
            ("数据列数", "columns"),
            ("缺失值数量", "missing"),
            ("重复行数量", "duplicates"),
            ("数值异常数量", "outliers"),
        ]
        records = []
        for name, key in fields:
            before = self.baseline.metrics[key]
            after = self.result.metrics[key]
            records.append({
                "指标": name,
                "原始数据": before,
                "当前数据": after,
                "变化": after - before,
            })
        before_score = self.baseline.score["score"]
        after_score = self.result.score["score"]
        records.append({
            "指标": "质量评分",
            "原始数据": before_score,
            "当前数据": after_score,
            "变化": round(after_score - before_score, 2),
        })
        return pd.DataFrame(records)
