"""Compatibility shim for the Yukta package layout.

This repository keeps the implementation under `yukta/yukta/`, while test
code and user imports expect `import yukta` to expose the public API.
This module forwards the package path and re-exports the inner package's
symbols so both `import yukta` and `import yukta.core...` keep working.
"""

from importlib import import_module
from pathlib import Path

_INNER_PACKAGE_DIR = Path(__file__).resolve().parent / "yukta"
if str(_INNER_PACKAGE_DIR) not in __path__:
    __path__.append(str(_INNER_PACKAGE_DIR))

_inner = import_module(".yukta", __name__)

for _name in getattr(_inner, "__all__", []):
    if hasattr(_inner, _name):
        globals()[_name] = getattr(_inner, _name)

__all__ = list(getattr(_inner, "__all__", []))
__version__ = getattr(_inner, "__version__", "0.0.0")
__author__ = getattr(_inner, "__author__", "")


def get_version():
    return getattr(_inner, "get_version")()


def quick_start():
    return getattr(_inner, "quick_start")()