"""Project configuration.

Reads the .env file at the project root and exposes small helpers.
Nothing secret lives in the code: secrets are read from Databricks at run time.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing setting {name}. Add it to your .env file.")
    return value


def mode():
    """'local' or 'databricks'. It is stored in every record we write."""
    return env("ENV_MODE", "local")


def export_dir():
    return Path(env("EXPORT_DIR", required=True))


def runs_dir():
    path = PROJECT_ROOT / "runs"
    path.mkdir(exist_ok=True)
    return path
