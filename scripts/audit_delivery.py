"""检查正式源码并整理已安装依赖的许可证原文，不扫描或输出运行日志内容。"""
import ast
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verification/final_v1.0"
DOCS = OUT / "docs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "main.py", *sorted((ROOT / "app").rglob("*.py"))]
    resources = sorted(p for p in (ROOT / "resources").rglob("*") if p.is_file())
    terms = ["TODO", "FIXME", "pass", "NotImplemented", "NotImplementedError", "mock", "dummy", "temp", "test123"]
    hits, absolute, suspect, copyrights, encodings = [], [], [], [], []
    for path in sources + resources:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        relative = path.relative_to(ROOT).as_posix()
        encodings.append({"file": relative, "utf8": True, "bom": raw.startswith(b"\xef\xbb\xbf")})
        assert "\ufffd" not in text and "\x00" not in text, relative
        if path.suffix == ".py":
            ast.parse(text, filename=relative)
        for number, line in enumerate(text.splitlines(), 1):
            for term in terms:
                pattern = r"\bpass\b" if term == "pass" else re.escape(term)
                if re.search(pattern, line, re.I):
                    hits.append({"file": relative, "line": number, "term": term})
            if re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", line):
                absolute.append({"file": relative, "line": number})
            if re.search(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*['\"][^'\"]+|sk-[A-Za-z0-9]{16,}|-----BEGIN .*PRIVATE KEY", line):
                suspect.append({"file": relative, "line": number})
            if re.search(r"copyright|©|版权所有", line, re.I):
                copyrights.append({"file": relative, "line": number})
    assert not absolute and not suspect, {"paths": absolute, "secrets": suspect}
    data = {"files": encodings, "keyword_hits": hits, "absolute_paths": absolute,
            "secret_candidates": suspect, "copyright_markers": copyrights}
    (OUT / "source_audit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    packages = [line.split("==")[0] for line in (ROOT / "requirements-lock.txt").read_text().splitlines() if "==" in line]
    licenses = DOCS / "third_party_licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in packages:
        dist = metadata.distribution(name)
        copied = []
        target = licenses / name
        for entry in dist.files or []:
            if ".dist-info/" not in str(entry).replace("\\", "/"):
                continue
            if "licenses" not in entry.parts and not any(word in entry.name.lower() for word in ["license", "licence", "copying", "notice", "copyright"]):
                continue
            origin = Path(dist.locate_file(entry))
            if origin.is_file():
                target.mkdir(exist_ok=True)
                destination = target / entry.name
                if destination.exists() and destination.read_bytes() != origin.read_bytes():
                    destination = target / (entry.parent.name + "-" + entry.name)
                shutil.copyfile(origin, destination)
                copied.append(destination.relative_to(DOCS).as_posix())
        classifiers = [c for c in dist.metadata.get_all("Classifier", []) if c.startswith("License ::")]
        label = dist.metadata.get("License-Expression") or "; ".join(classifiers) or dist.metadata.get("License", "未声明")
        rows.append({"name": name, "version": dist.version, "license_metadata": label[:400], "license_files": copied})
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        (licenses / "Python").mkdir(exist_ok=True)
        shutil.copyfile(python_license, licenses / "Python/LICENSE.txt")
        rows.append({"name": "Python", "version": sys.version.split()[0], "license_metadata": "见运行时随附 LICENSE.txt",
                     "license_files": ["third_party_licenses/Python/LICENSE.txt"]})
    (licenses / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"source_files": len(sources), "resources": len(resources), "keyword_hits": hits,
                      "private_paths": len(absolute), "secret_candidates": len(suspect),
                      "dependencies": [{"name": x["name"], "version": x["version"], "license_files": len(x["license_files"])} for x in rows]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
