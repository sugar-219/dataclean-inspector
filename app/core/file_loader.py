"""本地 CSV / XLSX / XLS 导入和原子导出。"""
from pathlib import Path
import csv
import os
import tempfile
import warnings
from numbers import Integral
import pandas as pd


def validate_file(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("文件不存在，请检查路径。")
    if path.suffix.lower() not in (".csv", ".xlsx", ".xls"):
        raise ValueError("不支持此格式，请选择 CSV、XLSX 或 XLS 文件。")
    if path.stat().st_size == 0:
        raise ValueError("文件为空，无法读取。")
    return path


def sheet_names(path):
    path = validate_file(path)
    if path.suffix.lower() == ".csv":
        return []
    try:
        with pd.ExcelFile(path, engine="xlrd" if path.suffix.lower() == ".xls" else "openpyxl") as book:
            return book.sheet_names
    except PermissionError as exc:
        raise ValueError("没有读取权限，请检查文件权限。") from exc
    except Exception as exc:
        raise ValueError("Excel 无法读取，文件可能损坏或已加密。") from exc


def read_preserving_identifiers(reader, **options):
    # 先检查原始文本，避免类型推断将 00123 变为 123；检查整列而非仅抽样。
    raw = reader(dtype=object, **options)
    text_columns = {
        col: object for col in raw.columns
        if raw[col].astype("string").str.fullmatch(r"\s*[+-]?0[0-9]+\s*", na=False).any()
    }
    del raw
    return reader(dtype=text_columns or None, **options)


def load_file(path, sheet=None):
    path = validate_file(path)
    encoding = ""
    try:
        if path.suffix.lower() == ".csv":
            for candidate in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
                try:
                    with path.open(encoding=candidate, newline="") as stream:
                        sample = stream.read(65536)
                    if "\x00" in sample:
                        raise ValueError("CSV 含有不支持的二进制内容或 UTF-16 编码，请另存为 UTF-8。")
                    try:
                        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
                    except csv.Error:
                        delimiter = ","
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", pd.errors.ParserWarning)
                        frame = read_preserving_identifiers(
                            pd.read_csv, filepath_or_buffer=path, encoding=candidate, sep=delimiter,
                            keep_default_na=False, low_memory=False, skip_blank_lines=False, index_col=False)
                    encoding = candidate
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("CSV 编码无法识别，请另存为 UTF-8 或 GB18030；不支持同一文件混用编码。")
        else:
            frame = read_preserving_identifiers(
                pd.read_excel, io=path, sheet_name=sheet if sheet is not None else 0,
                engine="xlrd" if path.suffix.lower() == ".xls" else "openpyxl", keep_default_na=False)
        if frame.empty:
            raise ValueError("文件没有数据记录，请确认包含表头及至少一行数据。")
        # 列名统一为不重复的字符串，保证所有按字段操作有明确对象。
        names, used = [], set()
        for name in frame.columns:
            base, suffix = str(name), 2
            title = base
            while title in used:
                title = f"{base}_{suffix}"
                suffix += 1
            used.add(title)
            names.append(title)
        frame.columns = names
        return frame.reset_index(drop=True), {"path": str(path.resolve()), "name": path.name,
                "size": path.stat().st_size, "sheet": sheet or "", "encoding": encoding}
    except PermissionError as exc:
        raise ValueError("没有读取权限，请关闭独占文件的程序或检查权限。") from exc
    except (pd.errors.EmptyDataError, pd.errors.ParserError, pd.errors.ParserWarning) as exc:
        raise ValueError("CSV 内容为空或行列格式不一致，请检查文件。") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("文件读取失败，请检查文件是否损坏、加密或格式不匹配。") from exc


def atomic_write(path, writer):
    """先写同目录临时文件，成功后替换，避免写入失败破坏已有文件。"""
    path = Path(path)
    handle, temporary = tempfile.mkstemp(prefix=".dataclean-", suffix=path.suffix, dir=path.parent)
    os.close(handle)
    try:
        writer(Path(temporary))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_data(frame, path, source=None, allow_overwrite=False):
    path = Path(path)
    if path.exists() and not allow_overwrite:
        raise ValueError("目标文件已存在，需要明确确认后才能覆盖。")
    if source and path.resolve() == Path(source).resolve() and not allow_overwrite:
        raise ValueError("不能直接覆盖原文件，请另存为新文件。")
    if path.suffix.lower() not in (".xlsx", ".csv"):
        raise ValueError("导出仅支持 XLSX 和 CSV。")

    def write(temporary):
        if path.suffix.lower() == ".csv":
            frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        else:
            # 字符串按文本写入，防止以 '=' 开头的原始值被作为公式执行。
            from openpyxl import Workbook
            from openpyxl.cell import WriteOnlyCell
            book = Workbook(write_only=True)
            sheet = book.create_sheet("清洗结果")
            for row in [list(frame.columns)]:
                cells = [WriteOnlyCell(sheet, value=str(v)) for v in row]
                for cell in cells:
                    cell.data_type = "s"
                sheet.append(cells)
            for row in frame.itertuples(index=False, name=None):
                cells = []
                for value in row:
                    # Excel 数值仅可靠保存 15 位有效数字，长整数用文本避免被舍入。
                    if isinstance(value, Integral) and abs(value) >= 10 ** 15:
                        value = str(value)
                    cell = WriteOnlyCell(sheet, value=None if pd.isna(value) else value)
                    if isinstance(value, str):
                        cell.data_type = "s"
                    cells.append(cell)
                sheet.append(cells)
            book.save(temporary)
    atomic_write(path, write)
