import os
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".matplotlib"))


@pytest.fixture
def sample():
    from app.core.file_loader import load_file
    return load_file(Path(__file__).parent / "fixtures/quality_cases.csv")[0]
