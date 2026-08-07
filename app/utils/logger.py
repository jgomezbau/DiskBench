"""Application logging configuration."""

import logging
from pathlib import Path


def configure_logging(directory: Path) -> None:
    """Write diagnostics to a user-owned state directory."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=directory / "diskbench.log",
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)
