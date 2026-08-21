"""dictshow: a terminal dictionary frontend powered by lexhint."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dictshow")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
