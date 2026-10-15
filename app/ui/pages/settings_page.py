from PySide6.QtWidgets import QFormLayout, QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox
from PySide6.QtCore import Signal
from app.core.cleaner import DATE_FORMATS
from app.ui.widgets.common import Page, button, muted


class SettingsPage(Page):
    save_requested = Signal(dict)

    def __init__(self, config, path):
        super().__init__("设置", "设置保存在本机，重启后仍然有效。调整检测参数后会使用同一参数重新计算前后评分。")
        form = QFormLayout()
        form.setVerticalSpacing(24)
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 100)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(round(config["missing_threshold"] * 100))
        self.iqr = QDoubleSpinBox()
        self.iqr.setRange(.1, 10)
        self.iqr.setSingleStep(.1)
        self.iqr.setValue(config["iqr_factor"])
        self.undo = QSpinBox()
        self.undo.setRange(1, 20)
        self.undo.setValue(config["undo_limit"])
        self.date = QComboBox()
        self.date.addItems(DATE_FORMATS)
        self.date.setCurrentText(config["date_format"])
        self.recent = QCheckBox("启动时显示最近打开文件")
        self.recent.setChecked(config["show_recent"])
        for label, widget in [("高缺失率阈值", self.threshold), ("异常值 IQR 系数", self.iqr), ("最多撤销步数", self.undo), ("默认日期格式", self.date), ("最近文件", self.recent)]:
            form.addRow(label, widget)
        self.layout.addLayout(form)
        self.layout.addWidget(button("保存设置", self.submit, True))
        self.layout.addWidget(muted(f"配置位置：{path}\n撤销历史保存在内存，大文件可适当减少步数。最近文件仅保存路径，数据内容不会写入配置。"))
        self.layout.addStretch()

    def submit(self):
        self.save_requested.emit({"missing_threshold": self.threshold.value() / 100, "iqr_factor": self.iqr.value(),
                                  "undo_limit": self.undo.value(), "date_format": self.date.currentText(), "show_recent": self.recent.isChecked()})
