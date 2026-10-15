from pathlib import Path
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QListWidget, QFrame, QSizePolicy
from PySide6.QtCore import Signal, Qt
from app import APP_NAME
from app.ui.widgets.common import Page, button, muted, stat_row, ScoreCard, section_title


class HomePage(Page):
    open_requested = Signal()
    recent_requested = Signal(str)
    quality_requested = Signal()

    def __init__(self):
        super().__init__(APP_NAME, "数据质量工作台  /  从发现问题到清洗交付")
        row, self.cards = stat_row(["数据行数", "字段数量", "质量问题项"])
        self.layout.addLayout(row)
        hero = QHBoxLayout()
        hero.setSpacing(16)
        self.score = ScoreCard()
        hero.addWidget(self.score, 2)
        source = QFrame()
        source.setObjectName("card")
        source_layout = QVBoxLayout(source)
        source_layout.setContentsMargins(24, 20, 24, 20)
        source_layout.setSpacing(12)
        source_layout.addWidget(section_title("当前数据"))
        self.state = QLabel("打开数据，开始质量分析")
        self.state.setObjectName("dataTitle")
        self.state.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.state.setWordWrap(True)
        source_layout.addWidget(self.state)
        self.summary = muted("将 Excel 或 CSV 拖入窗口，自动查看质量概览。")
        source_layout.addWidget(self.summary)
        source_layout.addStretch()
        actions = QHBoxLayout()
        actions.addWidget(button("打开 Excel / CSV", self.open_requested.emit, True))
        self.inspect = button("查看质量检测", self.quality_requested.emit)
        self.inspect.setEnabled(False)
        actions.addWidget(self.inspect)
        actions.addStretch()
        source_layout.addLayout(actions)
        hero.addWidget(source, 3)
        self.layout.addLayout(hero)
        recent_heading = QHBoxLayout()
        recent_heading.addWidget(section_title("最近打开"))
        recent_heading.addStretch()
        recent_heading.addWidget(muted("双击继续处理"))
        self.layout.addLayout(recent_heading)
        self.recent = QListWidget()
        self.recent.setObjectName("recentFiles")
        self.recent.setMinimumHeight(105)
        self.recent.itemDoubleClicked.connect(lambda item: self.recent_requested.emit(item.toolTip()))
        self.recent_empty = QLabel("还没有最近文件\n打开一份数据后，会在这里保留访问入口。", self.recent.viewport())
        self.recent_empty.setAlignment(Qt.AlignCenter)
        self.recent_empty.setObjectName("tableEmpty")
        self.recent_empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.layout.addWidget(self.recent, 1)
        self.layout.addWidget(muted("支持 XLSX / XLS / CSV    ·    全程本地处理    ·    清洗结果可另存导出"))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.recent_empty.setGeometry(self.recent.viewport().rect())

    def refresh(self, manager, config):
        self.recent.clear()
        if config["show_recent"]:
            for path in config["recent_files"]:
                self.recent.addItem(f"{Path(path).name}\n{Path(path).parent}")
                self.recent.item(self.recent.count() - 1).setToolTip(path)
        self.recent_empty.setVisible(self.recent.count() == 0)
        self.recent_empty.setText("还没有最近文件\n打开一份数据后，会在这里保留访问入口。" if config["show_recent"] else "最近文件已隐藏\n可在设置中开启显示。")
        if manager.result:
            result, m = manager.result, manager.result.metrics
            for card, value in zip(self.cards, [len(manager.frame), len(manager.frame.columns), result.issue_count]):
                card.set_value(value)
            self.cards[0].set_detail(f"重复记录 {m['duplicates']:,} 行")
            self.cards[1].set_detail(f"缺失单元格 {m['missing']:,} 个")
            severe = sum(issue.severity == "严重" for issue in result.issues)
            self.cards[2].set_detail(f"其中严重问题 {severe} 项")
            self.score.set_score(result.score)
            name = manager.metadata["name"]
            self.state.setText(name[:64] + ("…" if len(name) > 64 else ""))
            self.state.setToolTip(manager.metadata.get("path", name))
            self.summary.setText(f"{m['rows']:,} 行 · {m['columns']} 个字段\n已完成检测，可查看问题详情或继续清洗。")
            self.inspect.setEnabled(True)
