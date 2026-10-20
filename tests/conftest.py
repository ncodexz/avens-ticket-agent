import core.config  # noqa: F401  (loads the .env file so EXPORT_DIR is available)
import os

import pytest

needs_export = pytest.mark.skipif(
    not os.getenv("EXPORT_DIR"), reason="EXPORT_DIR (real exported tickets) is not set"
)
