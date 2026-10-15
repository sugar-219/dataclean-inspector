"""启动真实 Windows 平台的源码版和打包版，等待真实退出码。"""
from pathlib import Path
import json
import os
import subprocess
import sys


def run():
    root = Path(__file__).resolve().parents[1]
    directory = root / "verification/native-smoke"
    directory.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="windows", DATACLEAN_HOME=str(directory))
    executable = root / "dist/数据清洗与质量检测工具/数据清洗与质量检测工具.exe"
    cases = {"源码Windows窗口": [sys.executable, str(root / "main.py"), "--smoke-test", "--open", str(root / "samples/sales_data.csv")],
             "打包Windows窗口": [str(executable), "--smoke-test", "--open", str(root / "samples/student_data.xlsx")]}
    results = {}
    for name, command in cases.items():
        completed = subprocess.run(command, cwd=root, env=environment, capture_output=True, timeout=60)
        results[name] = {"exit_code": completed.returncode, "stderr": completed.stderr.decode("utf-8", errors="replace")}
        assert completed.returncode == 0, results[name]
        print(name, "PASS", flush=True)
    (root / "verification/package_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    run()
