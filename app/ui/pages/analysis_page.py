import logging
from collections import Counter
import numpy as np
from PySide6.QtWidgets import QTabWidget, QHBoxLayout, QComboBox, QLabel, QFrame, QVBoxLayout, QSplitter, QSizePolicy
from PySide6.QtCore import Qt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib import rcParams
from app.ui.widgets.common import Page
from app.ui.widgets.data_table import DataTable

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
rcParams["axes.unicode_minus"] = False


class AnalysisPage(Page):
    def __init__(self):
        super().__init__("数据分析", "统计指标基于当前数据；数值统计忽略缺失值与无法解析的内容。")
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.numeric = DataTable(formatted=True, empty_text="暂无数值统计\n导入包含数值字段的数据后查看。")
        self.text = DataTable(formatted=True, empty_text="暂无非数值字段统计")
        tabs.addTab(self.numeric, "数值统计")
        tabs.addTab(self.text, "文本 / 日期 / 布尔统计")
        workspace = QSplitter(Qt.Vertical)
        workspace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(tabs)
        chart_panel = QFrame()
        chart_panel.setObjectName("card")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(16, 16, 16, 12)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("图表类型"))
        self.kind = QComboBox()
        self.kind.addItems(["缺失率柱状图", "数据类型分布图", "数值字段分布直方图", "数据问题类型统计图"])
        self.column = QComboBox()
        controls.addWidget(self.kind)
        controls.addWidget(self.column)
        controls.addStretch()
        chart_layout.addLayout(controls)
        self.figure = Figure(figsize=(8, 3), dpi=100, facecolor="white")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(200)
        chart_layout.addWidget(self.canvas, 1)
        self.message = QLabel("导入后可查看图表。")
        self.message.setObjectName("muted")
        chart_layout.addWidget(self.message)
        workspace.addWidget(chart_panel)
        workspace.setSizes([190, 370])
        self.layout.addWidget(workspace, 1)
        self.result = None
        self.analysis = {}
        self.kind.currentTextChanged.connect(self.draw)
        self.column.currentTextChanged.connect(self.draw)
        self.draw()

    def refresh(self, manager):
        self.result, self.analysis = manager.result, manager.analysis
        if self.result is None:
            return
        self.numeric.set_frame(self.analysis["numeric"])
        self.text.set_frame(self.analysis["text"])
        selected = self.column.currentText()
        self.column.blockSignals(True)
        self.column.clear()
        self.column.addItems(list(self.analysis["histograms"]))
        if selected in self.analysis["histograms"]:
            self.column.setCurrentText(selected)
        self.column.blockSignals(False)
        self.draw()

    def draw(self, *_):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        kind = self.kind.currentText()
        self.column.setVisible(kind == "数值字段分布直方图")
        self.message.setText("")
        if self.result is None:
            ax.set_axis_off()
            ax.text(.5, .5, "导入数据后生成图表", ha="center", va="center", transform=ax.transAxes)
        else:
            try:
                fields = self.result.fields
                if kind == "缺失率柱状图":
                    view = fields.sort_values("缺失率", ascending=False).head(30)
                    ax.bar(view["字段名"], view["缺失率"] * 100, color="#19877c", width=.6)
                    ax.set_ylabel("缺失率（%）")
                    ax.set_ylim(0, max(5, float(view["缺失率"].max() * 110) if len(view) else 5))
                    self.message.setText("按缺失率降序展示前 30 个字段。")
                elif kind == "数据类型分布图":
                    counts = fields["推断类型"].value_counts()
                    if len(counts):
                        ax.pie(counts.values, labels=counts.index, autopct="%1.0f%%", colors=["#19877c", "#5e7bce", "#e9ad56", "#ad8cc8", "#84b8c4", "#bbcad2"], wedgeprops={"width": .48, "edgecolor": "white"})
                elif kind == "数值字段分布直方图":
                    name = self.column.currentText()
                    if name in self.analysis.get("histograms", {}):
                        counts, edges = self.analysis["histograms"][name]
                        ax.bar(edges[:-1], counts, width=np.diff(edges), align="edge", color="#5e7bce", edgecolor="white")
                        ax.set_xlabel(name)
                        ax.set_ylabel("记录数")
                    else:
                        ax.text(.5, .5, "没有可绘制的数值字段", ha="center", transform=ax.transAxes)
                else:
                    counts = Counter(i.kind for i in self.result.issues)
                    ax.bar(list(counts), list(counts.values()), color="#dca357", width=.6)
                    ax.set_ylabel("问题项数（按规则 / 字段聚合）")
                if kind != "数据类型分布图":
                    ax.tick_params(axis="x", labelrotation=25, labelsize=9)
                    ax.spines[["top", "right", "left"]].set_visible(False)
                    ax.spines["bottom"].set_color("#dae3eb")
                    ax.tick_params(colors="#6b7d8d")
                    ax.grid(axis="y", alpha=.15)
                    ax.set_axisbelow(True)
                ax.set_title(kind, loc="left", fontsize=12, pad=14)
            except Exception:
                logging.getLogger("dataclean").exception("图表生成失败")
                self.message.setText("图表生成失败，请检查字段内容；统计表仍可使用。")
        self.figure.tight_layout(pad=2)
        self.canvas.draw_idle()
