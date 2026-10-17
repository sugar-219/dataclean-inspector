# 数据清洗与质量检测工具软件

一个在本机运行的中文 Windows 数据清洗与质量检测工具，支持 Excel / CSV 导入、质量检测、清洗、统计分析及结果导出。基于 Python、PySide6 和 pandas 开发，无需后端服务或在线 API。

## 功能

- **导入与预览**：支持 XLSX、XLS、CSV、Excel 工作表选择及文件拖入；表格分页预览、搜索和排序。
- **质量检测**：缺失值、重复行、空字符串、首尾空白、数值异常、类型异常、日期异常、唯一值占比、常量列、高缺失率，共十类规则。
- **质量评分**：按完整性、唯一性、一致性、有效性四个维度评分，展示问题位置和处理建议。
- **数据清洗**：十二类清洗操作、六种缺失值填充方式、严格类型转换；清洗前预览影响数量及改动样例，确认后应用，支持最多 20 步撤销及前后对比。
- **分析与报告**：字段统计、四类图表、离线 HTML 检测报告。
- **导出与记录**：清洗结果导出为 XLSX / CSV，操作记录导出为 CSV；支持本地配置和日志。

## 安装与运行

已验证环境为 Windows 11 64 位、标准 Windows CPython 3.12。请在项目根目录打开 PowerShell，执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe main.py
```

安装完成后，也可以双击 `run.bat` 启动。首次安装依赖需要联网，程序日常运行在本地完成。建议使用标准 Windows Python，避免与 MSYS 或其他工具链混用。

打开指定文件：

```powershell
.\.venv\Scripts\python.exe main.py --open samples\sales_data.csv
```

窗口默认尺寸为 1280 × 800，最小尺寸为 1100 × 700。

## 使用流程

1. 在首页打开 Excel / CSV，或拖入一个文件；Excel 可选择工作表。
2. 在“数据预览”查看字段、搜索数据、点击表头排序。
3. 在“质量检测”选择问题分类，双击问题查看行号、原始值及建议。
4. 在“数据清洗”选择操作、字段和参数，点击“执行清洗”先查看预览，再“确认应用”；取消不会修改数据。应用后查看检测结果，需要时撤销。
5. 在“数据分析”查看统计和图表，在“检测报告”导出 HTML。
6. 使用顶部“导出数据”保存 XLSX / CSV，在“操作记录”导出会话记录。

`samples/` 提供三份故意含有缺失、重复、异常、日期错误和空格等问题的模拟数据，每份 123 条记录，可直接用于体验功能。

## 数据处理规则

- 缺失值包括 NaN、None、NaT、空字符串和纯空白文本，合法文本 `NA` 不会在导入时被当作缺失值。
- 导入时自动保留 `00123` 这类带前导零的整数文本所在列的原始值，普通数值列仍自动识别。Excel 中仅靠单元格数字格式显示的前导零不属于存储的文本，无法据此恢复；需要时先在 Excel 中将编号存为文本。
- 重复行按全部字段完全相同判断，每组保留第一条；空格不同的记录在清洗前不会被当作相同记录。
- IQR 检测至少需要 4 个有限数值，默认系数为 1.5。异常提示需结合业务确认。
- 评分权重为完整性 35%、唯一性 25%、一致性 20%、有效性 20%，具体分母及扣分在报告中列示。
- 类型转换遇到无效值会使整次操作失败并保留原数据；整数转换拒绝截断小数。
- 清洗只修改当前内存数据，原始文件不会自动覆盖。导出不保留原 Excel 的公式、样式、合并单元格、其他工作表或宏。
- 清洗预览最多展示 100 条改动样例，影响数量按整份数据计算；删除操作的行号对应清洗前的位置。确认后应用预览的候选结果，取消不增加撤销历史或操作记录。
- 未保存提示以最近一次成功导出的数据为基准；导出后再撤销，如果数据与已导出的版本不同，退出或打开新文件时仍会提醒。尚未导出时以导入的数据为基准。
- Excel 导出会将以 `=` 开头的原始字符串及超过 15 位的整数按文本保存；CSV 在其他表格软件中的解释由该软件决定。
- 行号从 1 开始，不含表头。预览搜索和排序不会改变底层数据；删除记录后行号会重新编号。

## 项目结构

```text
dataclean-inspector/
├─ main.py                   # 程序入口
├─ app/
│  ├─ core/                  # 读取、检测、评分、清洗、统计、报告和撤销
│  ├─ models/                # 问题及操作记录模型
│  ├─ ui/                    # 窗口、页面、虚拟表格与后台线程
│  └─ utils/                 # 配置、日志、资源路径和数据语义
├─ resources/                # 主题、图标及 HTML 报告模板
├─ samples/                  # 三份模拟数据
├─ tests/                    # 核心和界面测试、测试数据
├─ scripts/                  # 构建、示例生成和验证工具
├─ requirements.txt          # 依赖版本范围
├─ requirements-lock.txt     # 已验证的具体依赖版本
├─ pytest.ini
├─ run.bat
├─ build.bat
└─ README.md
```

业务处理使用 pandas DataFrame；界面通过 QThread 执行耗时任务，通过 QAbstractTableModel 展示表格。配置和日志仅保存在本地：源码运行时位于项目目录，打包版位于 `%LOCALAPPDATA%\DataCleanInspector\`。可通过 `DATACLEAN_HOME` 指定其他可写目录。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe main.py --smoke-test
```

界面截图与十万行数据流程验证：

```powershell
.\.venv\Scripts\python.exe scripts\verify_desktop.py --screenshots-only
.\.venv\Scripts\python.exe scripts\verify_desktop.py
```

验证产物写入 `verification/`，不会提交到仓库。完整数据流程验证会产生较大的临时数据文件。

## 构建 Windows 程序

```powershell
.\build.bat
```

构建结果位于 `dist\数据清洗与质量检测工具\`。分发时需要保留整个目录，包括 `_internal`；使用者无需另装 Python。构建后可运行：

```powershell
.\.venv\Scripts\python.exe scripts\verify_package.py
```

修改图标资源后，重新生成 Qt 资源模块：

```powershell
.\.venv\Scripts\pyside6-rcc.exe resources\icons.qrc -o app\ui\widgets\icon_resources.py
```

## 当前限制

- 一次处理一个文件、一个工作表，暂不支持多文件批处理、直接编辑单元格和跨会话恢复。
- 撤销历史只在内存中保存，退出程序后清除；暂不支持重做。
- 基于内存处理数据，大文件需结合可用内存评估并适当减少撤销步数。
- CSV 支持 UTF-8、UTF-8-SIG、GBK、GB18030，不支持同一文件混用编码。
- 日期推断有适用范围，含糊的月日顺序应先规范化。
- 程序导出 HTML 报告，可通过浏览器打印为 PDF，暂不提供直接导出 PDF。
