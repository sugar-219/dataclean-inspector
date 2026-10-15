import json
import pandas as pd
from PySide6.QtWidgets import QHBoxLayout, QLabel, QComboBox, QDialog, QVBoxLayout, QFrame, QGridLayout, QProgressBar
from PySide6.QtCore import Signal
from app.ui.widgets.common import Page, button, muted, ScoreCard, section_title
from app.ui.widgets.data_table import DataTable


class QualityPage(Page):
    detect_requested = Signal()

    def __init__(self):
        super().__init__("质量检测", "十类规则定位数据问题；提示级问题请结合实际业务判断。")
        overview = QHBoxLayout()
        overview.setSpacing(16)
        self.score = ScoreCard()
        overview.addWidget(self.score, 2)
        dimensions_card = QFrame()
        dimensions_card.setObjectName("card")
        grid = QGridLayout(dimensions_card)
        grid.setContentsMargins(24, 16, 24, 16)
        grid.addWidget(section_title("评分组成"), 0, 0, 1, 3)
        self.dimension_bars = {}
        for row, name in enumerate(["完整性", "唯一性", "一致性", "有效性"], 1):
            grid.addWidget(QLabel(name), row, 0)
            bar = QProgressBar()
            bar.setObjectName("dimensionBar")
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setTextVisible(False)
            value = QLabel("—")
            grid.addWidget(bar, row, 1)
            grid.addWidget(value, row, 2)
            self.dimension_bars[name] = (bar, value)
        grid.setColumnStretch(1, 1)
        overview.addWidget(dimensions_card, 3)
        self.layout.addLayout(overview)
        self.summary = QHBoxLayout()
        self.count_label = section_title("问题清单")
        self.summary.addWidget(self.count_label)
        self.summary.addStretch()
        self.level_labels = {}
        for level in ["严重", "警告", "提示"]:
            label = QLabel(f"{level}  —")
            label.setObjectName("rating")
            label.setProperty("level", level)
            self.level_labels[level] = label
            self.summary.addWidget(label)
        self.layout.addLayout(self.summary)
        actions = QHBoxLayout()
        actions.addWidget(button("开始质量检测", self.detect_requested.emit, True))
        self.category = QComboBox()
        self.category.addItems(["全部", "缺失值", "重复值", "异常值", "格式异常", "类型异常", "其他"])
        self.category.currentTextChanged.connect(self.filter_issues)
        actions.addWidget(self.category)
        actions.addStretch()
        actions.addWidget(button("查看选中问题详情", self.show_details))
        self.layout.addLayout(actions)
        self.table = DataTable(status_columns=("严重程度",), empty_text="暂无检测结果\n打开数据后自动检测，或点击“开始质量检测”。")
        self.table.doubleClicked.connect(self.show_details)
        self.layout.addWidget(self.table, 1)
        self.layout.addWidget(muted("问题总项按规则和字段汇总；同一单元格可能命中多条规则。双击可查看完整行号及原值。"))
        self.issues, self.filtered, self.frame = [], [], pd.DataFrame()

    def refresh(self, manager):
        self.frame = manager.frame
        if not manager.result:
            return
        result = manager.result
        self.issues = result.issues
        self.count_label.setText(f"问题清单  ·  {result.issue_count} 项")
        self.score.set_score(result.score)
        for level, label in self.level_labels.items():
            label.setText(f"{level}  {sum(i.severity == level for i in self.issues)}")
        for name, (bar, label) in self.dimension_bars.items():
            value = result.score["dimensions"].get(name)
            bar.setValue(round(value * 10) if value is not None else 0)
            label.setText(f"{value:.1f}" if value is not None else "—")
        self.filter_issues()

    def filter_issues(self):
        category = self.category.currentText()
        self.filtered = [i for i in self.issues if category == "全部" or i.category == category]
        rows = [{"问题类型": i.kind, "字段": i.column, "行号 / 影响范围": f"{i.count} 处；" + ",".join(map(str, i.rows[:5])) + ("…" if i.count > 5 else ""),
                 "问题描述": i.description, "严重程度": i.severity, "建议处理方式": i.suggestion} for i in self.filtered]
        self.table.set_frame(pd.DataFrame(rows, columns=["问题类型", "字段", "行号 / 影响范围", "问题描述", "严重程度", "建议处理方式"]))
        self.table.empty.setText("当前分类没有发现问题\n可以切换其他分类，查看完整检测结果。" if self.frame.size else "暂无检测结果\n打开数据后即可查看问题清单。")
        for col, width in enumerate([125, 100, 155, 220, 90, 240]):
            self.table.setColumnWidth(col, width)

    def show_details(self, *_):
        row = self.table.currentIndex().row()
        if row < 0 or row >= len(self.filtered):
            return
        issue = self.filtered[row]
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{issue.kind} · {issue.column}")
        dialog.resize(820, 540)
        layout = QVBoxLayout(dialog)
        layout.addWidget(muted(issue.description + "\n建议：" + issue.suggestion + f"\n共影响 {issue.count} 处；行号从 1 开始，不包含表头。"))
        if issue.details:
            layout.addWidget(muted(json.dumps(issue.details, ensure_ascii=False)))
        table = DataTable()
        layout.addWidget(table, 1)
        controls = QHBoxLayout()
        previous, next_btn, label = button("上一页"), button("下一页"), QLabel()
        controls.addWidget(previous)
        controls.addWidget(label)
        controls.addWidget(next_btn)
        controls.addStretch()
        controls.addWidget(button("关闭", dialog.accept))
        layout.addLayout(controls)
        state = [0]

        def render(delta=0):
            state[0] += delta
            start = state[0] * 500
            positions = [v - 1 for v in issue.rows[start:start + 500]]
            table.set_frame(self.frame, positions)
            label.setText(f"第 {state[0] + 1} / {max(1, (issue.count + 499) // 500)} 页")
            previous.setEnabled(state[0] > 0)
            next_btn.setEnabled(start + 500 < issue.count)

        previous.clicked.connect(lambda: render(-1))
        next_btn.clicked.connect(lambda: render(1))
        render()
        dialog.exec()
