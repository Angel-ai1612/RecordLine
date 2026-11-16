from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


TEST_ROOT = Path(tempfile.mkdtemp(prefix="doctrace-tests-"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DOCTRACE_DATABASE_URL"] = f"sqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
os.environ["DOCTRACE_FILES_DIR"] = str(TEST_ROOT / "files")

