import os
from pathlib import Path


def _data_dir() -> Path:
    """Return the base data directory, overridable via PIPELINE_DATA_DIR env var."""
    return Path(os.environ.get("PIPELINE_DATA_DIR", "data"))
