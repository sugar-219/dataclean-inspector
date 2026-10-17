from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QComboBox, QLineEdit, QListWidget,
    QAbstractItemView, QFormLayout, QFrame, QSplitter, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from app.core.cleaner import OPERATIONS, DATE_FORMATS, WHOLE_TABLE_OPERATIONS
from app.ui.widgets.common import Page, button, muted, section_title
from app.ui.widgets.data_table import DataTable


class CleaningPage(Page):
    apply_requested = Signal(str, list, dict)
    undo_requested = Signal()

    def __init__(self):
        super().__init__("数据清洗", "选择操作与字段后预览改动，确认应用后自动重新检测，并保留撤销状态。")
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        fields = QFrame()
        fields.setObjectName("card")
        field_layout = QVBoxLayout(fields)
        field_layout.setContentsMargins(16, 16, 16, 16)
        field_layout.addWidget(section_title("选择字段"))
        self.selection_label = muted("点击字段可多选")
        field_layout.addWidget(self.selection_label)
        self.columns = QListWidget()
        self.columns.setSelectionMode(QAbstractItemView.MultiSelection)
        field_layout.addWidget(self.columns)
        self.select_all = button("选择全部字段", self.columns.selectAll)
        field_layout.addWidget(self.select_all)
        self.columns.itemSelectionChanged.connect(self.update_selection)
        splitter.addWidget(fields)
        options = QFrame()
        options.setObjectName("card")
        self.form = QFormLayout(options)
        self.form.setContentsMargins(22, 18, 22, 18)
        self.form.setVerticalSpacing(12)
        self.form.addRow(section_title("配置清洗操作"))
        self.operation = QComboBox()
        self.operation.addItems(OPERATIONS)
        self.form.addRow("清洗操作", self.operation)
        self.method = QComboBox()
        self.method.addItems(["固定值", "均值", "中位数", "众数", "前向填充", "后向填充"])
        self.value = QLineEdit()
        self.value.setPlaceholderText("输入填充内容")
        self.case = QComboBox()
        self.case.addItems(["全部大写", "全部小写"])
        self.old, self.new = QLineEdit(), QLineEdit()
        self.old.setPlaceholderText("按文本子串匹配，不使用正则表达式")
        self.new.setPlaceholderText("留空表示删除匹配的文本")
        self.target = QComboBox()
        self.target.addItems(["整数", "小数", "字符串", "日期"])
        self.date_format = QComboBox()
        self.date_format.addItems(DATE_FORMATS)
        self.rows, self.name = QLineEdit(), QLineEdit()
        self.rows.setPlaceholderText("例如 1,3-5；当前数据行号，不包含表头")
        self.parameters = {
            "method": ("填充方式", self.method),
            "value": ("固定值", self.value),
            "case": ("转换方式", self.case),
            "old": ("待替换文本", self.old),
            "new": ("替换为", self.new),
            "target": ("目标类型", self.target),
            "date_format": ("日期格式", self.date_format),
            "rows": ("删除行号", self.rows),
            "name": ("新字段名", self.name),
        }
        for label, widget in self.parameters.values():
            self.form.addRow(label, widget)
        self.hint = muted("")
        self.form.addRow(self.hint)
        self.apply_button = button("执行清洗", self.submit, True)
        self.form.addRow(self.apply_button)
        self.operation.currentTextChanged.connect(self.update_options)
        self.method.currentTextChanged.connect(self.update_options)
        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        options_scroll.setFrameShape(QFrame.NoFrame)
        options_scroll.setWidget(options)
        splitter.addWidget(options_scroll)
        splitter.setSizes([250, 620])
        workspace = QSplitter(Qt.Vertical)
        workspace.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        workspace.setChildrenCollapsible(False)
        workspace.addWidget(splitter)
        compare_panel = QFrame()
        compare_panel.setObjectName("card")
        compare_layout = QVBoxLayout(compare_panel)
        compare_layout.setContentsMargins(16, 12, 16, 12)
        actions = QHBoxLayout()
        actions.addWidget(section_title("清洗前后对比"))
        actions.addStretch()
        self.undo_button = button("撤销上一步", self.undo_requested.emit)
        actions.addWidget(self.undo_button)
        compare_layout.addLayout(actions)
        self.delta = muted("导入数据后查看质量变化。")
        compare_layout.addWidget(self.delta)
        self.comparison = DataTable(formatted=True, empty_text="暂无对比数据\n清洗后自动展示变化，可撤销恢复。")
        self.comparison.setMinimumHeight(125)
        compare_layout.addWidget(self.comparison, 1)
        workspace.addWidget(compare_panel)
        workspace.setSizes([330, 240])
        self.layout.addWidget(workspace, 1)
        self.threshold = .3
        self.update_options()

    def active_keys(self):
        operation = self.operation.currentText()
        if operation == "缺失值填充":
            if self.method.currentText() == "固定值":
                return ["method", "value"]
            return ["method"]
        parameters = {
            "大小写转换": ["case"],
            "文本批量替换": ["old", "new"],
            "数据类型转换": ["target"],
            "日期格式统一": ["date_format"],
            "删除指定行": ["rows"],
            "字段重命名": ["name"],
        }
        return parameters.get(operation, [])

    def update_options(self):
        active_keys = self.active_keys()
        for key, (_, widget) in self.parameters.items():
            self.form.setRowVisible(widget, key in active_keys)
        global_op = self.operation.currentText() in WHOLE_TABLE_OPERATIONS
        self.columns.setEnabled(not global_op)
        self.select_all.setEnabled(not global_op)
        self.update_selection()
        hints = {"删除高缺失字段": f"删除缺失率 ≥ {self.threshold:.0%} 的字段（阈值可在设置调整）。",
                 "删除指定行": "行号始终对应预览左侧数据行号；清洗后会重新编号。",
                 "数据类型转换": "转换失败将保留整次操作之前的数据，并说明无效值。",
                 "字段重命名": "仅选择一个字段，新名称不能与其他字段重复。"}
        self.hint.setText(hints.get(self.operation.currentText(), "整表操作无需选择字段；其他操作只作用于选中字段。"))

    def update_selection(self):
        if self.operation.currentText() in WHOLE_TABLE_OPERATIONS:
            self.selection_label.setText("整表操作，无需选择字段")
        else:
            self.selection_label.setText(f"已选 {len(self.columns.selectedItems())} / {self.columns.count()} 个字段")

    def submit(self):
        params = {}
        for key in self.active_keys():
            widget = self.parameters[key][1]
            params[key] = widget.currentText() if isinstance(widget, QComboBox) else widget.text()
        if self.operation.currentText() == "删除高缺失字段":
            params["threshold"] = self.threshold
        columns = [item.text() for item in self.columns.selectedItems()] if self.columns.isEnabled() else []
        self.apply_requested.emit(self.operation.currentText(), columns, params)

    def refresh(self, manager, config):
        selected = {item.text() for item in self.columns.selectedItems()}
        self.columns.clear()
        for col in manager.frame.columns:
            self.columns.addItem(str(col))
            self.columns.item(self.columns.count() - 1).setSelected(col in selected)
        self.threshold = config["missing_threshold"]
        self.date_format.setCurrentText(config["date_format"])
        self.undo_button.setText(f"撤销上一步（剩余 {len(manager.undo)} 步）")
        self.undo_button.setEnabled(len(manager.undo) > 0)
        self.comparison.set_frame(manager.comparison())
        if manager.result:
            before, after = manager.baseline.score["score"], manager.result.score["score"]
            self.delta.setText(f"质量评分  {before:.2f} → {after:.2f}    ·    变化 {after - before:+.2f} 分")
        self.update_options()
