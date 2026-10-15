"""实际执行无测试参数的 main.py / exe，确认原生窗口后正常发送关闭消息。"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def process_family(process_id):
    """Windows 虚拟环境的 python.exe 可能将界面放在子解释器进程中。"""
    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = Entry()
    entry.dwSize = ctypes.sizeof(entry)
    parents = {}
    try:
        available = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            available = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    family = {process_id}
    while True:
        updated = family | {pid for pid, parent in parents.items() if parent in family}
        if updated == family:
            return family
        family = updated


def visible_window(process_id):
    user32 = ctypes.windll.user32
    family = process_family(process_id)
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

    @callback_type
    def callback(handle, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        if pid.value in family and user32.IsWindowVisible(handle):
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(handle, title, 256)
            if title.value == "数据清洗与质量检测工具软件 V1.0":
                found.append(handle)
        return True
    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "verification/release_check"
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, QT_QPA_PLATFORM="windows", DATACLEAN_HOME=str(output / "native"))
    cases = {"python main.py": [sys.executable, "main.py"]}
    if "--package" in sys.argv:
        cases["Windows exe"] = [str(root / "dist/数据清洗与质量检测工具/数据清洗与质量检测工具.exe")]
    results = {}
    for name, command in cases.items():
        process = subprocess.Popen(command, cwd=root, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 30
            handle = None
            while process.poll() is None and time.monotonic() < deadline:
                handle = visible_window(process.pid)
                if handle:
                    break
                time.sleep(.1)
            assert handle, f"{name} 未出现正常主窗口"
            time.sleep(1)
            user32 = ctypes.windll.user32
            user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            assert user32.PostMessageW(handle, 0x0010, 0, 0)
            stdout, stderr = process.communicate(timeout=15)
            results[name] = {"window_visible": True, "exit_code": process.returncode,
                             "stderr": stderr.decode("utf-8", errors="replace")}
            assert process.returncode == 0 and not stderr, results[name]
            print(name, "原生窗口启动及正常关闭通过", flush=True)
        finally:
            if process.poll() is None:
                # 只终止本验证脚本启动的进程树，避免失败后遗留窗口。
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
                process.communicate(timeout=10)
    (output / "native_launch.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
