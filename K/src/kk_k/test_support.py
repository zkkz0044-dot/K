from __future__ import annotations

import tempfile

from .isolation import PROJECT_ROOT, project_path

TEST_ROOT = project_path(PROJECT_ROOT / ".test_tmp")
TEST_ROOT.mkdir(parents=True, exist_ok=True)


def project_tempdir():
    return tempfile.TemporaryDirectory(dir=str(TEST_ROOT))
