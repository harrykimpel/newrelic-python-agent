"""This module implements a global cache for tracking any traces.

"""

import sys
import random
import threading
import weakref
import traceback
import logging

try:
    import thread
except ImportError:
    import _thread as thread

from newrelic.core.config import global_settings
from newrelic.core.loop_node import LoopNode

_logger = logging.getLogger(__name__)


def current_task():
    asyncio = sys.modules.get('asyncio')
    if not asyncio:
        return

    current_task = getattr(asyncio, 'current_task', None)
    if current_task is None:
        current_task = getattr(asyncio.Task, 'current_task', None)

    try:
        return current_task()
    except:
        pass


class TraceCache(object):

    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def current_thread_id(self):
        """Returns the thread ID for the caller.

        When greenlets are present and we detect we are running in the
        greenlet then we use the greenlet ID instead of the thread ID.

        """

        greenlet = sys.modules.get('greenlet')

        if greenlet:
            # Greenlet objects are maintained in a tree structure with
            # the 'parent' attribute pointing to that which a specific
            # instance is associated with. Only the root node has no
            # parent. This node is special and is the one which
            # corresponds to the original thread where the greenlet
            # module was imported and initialised. That root greenlet is
            # never actually running and we should always ignore it. In
            # all other cases where we can obtain a current greenlet,
            # then it should indicate we are running as a greenlet.

            current = greenlet.getcurrent()
            if current is not None and current.parent:
                return id(current)

        task = current_task()
        if task is not None:
            return id(task)

        return thread.get_ident()

    def current_transaction(self):
        """Return the transaction object if one exists for the currently
        executing thread.

        """

        trace = self._cache.get(self.current_thread_id())
        return trace and trace.transaction

    def current_trace(self):
        return self._cache.get(self.current_thread_id())

    def active_threads(self):
        """Returns an iterator over all current stack frames for all
        active threads in the process. The result for each is a tuple
        consisting of the thread identifier, a categorisation of the
        type of thread, and the stack frame. Note that we actually treat
        any greenlets as threads as well. In that case the thread ID is
        the id() of the greenlet.

        This is in this class for convenience as needs to access the
        currently active transactions to categorise transaction threads
        as being for web transactions or background tasks.

        """

        # First yield up those for real Python threads.

        for thread_id, frame in sys._current_frames().items():
            trace = self._cache.get(thread_id)
            transaction = trace and trace.transaction
            if transaction is not None:
                if transaction.background_task:
                    yield transaction, thread_id, 'BACKGROUND', frame
                else:
                    yield transaction, thread_id, 'REQUEST', frame
            else:
                # Note that there may not always be a thread object.
                # This is because thread could have been created direct
                # against the thread module rather than via the high
                # level threading module. Categorise anything we can't
                # obtain a name for as being 'OTHER'.

                thread = threading._active.get(thread_id)
                if thread is not None and thread.getName().startswith('NR-'):
                    yield None, thread_id, 'AGENT', frame
                else:
                    yield None, thread_id, 'OTHER', frame

        # Now yield up those corresponding to greenlets. Right now only
        # doing this for greenlets in which any active transactions are
        # running. We don't have a way of knowing what non transaction
        # threads are running.

        debug = global_settings().debug

        if debug.enable_coroutine_profiling:
            for thread_id, trace in self._cache.items():
                transaction = trace.transaction
                if transaction and transaction._greenlet is not None:
                    gr = transaction._greenlet()
                    if gr and gr.gr_frame is not None:
                        if transaction.background_task:
                            yield (transaction, thread_id,
                                    'BACKGROUND', gr.gr_frame)
                        else:
                            yield (transaction, thread_id,
                                    'REQUEST', gr.gr_frame)

    def save_trace(self, trace):
        """Saves the specified trace away under the thread ID of
        the current executing thread. Will also cache a reference to the
        greenlet if using coroutines. This is so we can later determine
        the stack trace for a transaction when using greenlets.

        """

        thread_id = trace.thread_id

        if (thread_id in self._cache and
                self._cache[thread_id].root is not trace.root):
            _logger.error('Runtime instrumentation error. Attempt to '
                    'save a trace from an inactive transaction. '
                    'Report this issue to New Relic support.\n%s',
                    ''.join(traceback.format_stack()[:-1]))

            raise RuntimeError('transaction already active')

        self._cache[thread_id] = trace

        # We judge whether we are actually running in a coroutine by
        # seeing if the current thread ID is actually listed in the set
        # of all current frames for executing threads. If we are
        # executing within a greenlet, then thread.get_ident() will
        # return the greenlet identifier. This will not be a key in
        # dictionary of all current frames because that will still be
        # the original standard thread which all greenlets are running
        # within.

        trace._greenlet = None

        if hasattr(sys, '_current_frames'):
            if thread_id not in sys._current_frames():
                greenlet = sys.modules.get('greenlet')
                if greenlet:
                    trace._greenlet = weakref.ref(greenlet.getcurrent())

                asyncio = sys.modules.get('asyncio')
                if asyncio and not hasattr(trace, '_task'):
                    task = current_task()
                    trace._task = task

    def pop_current(self, trace):
        """Restore the trace's parent under the thread ID of the current
        executing thread."""

        if hasattr(trace, '_task'):
            delattr(trace, '_task')

        thread_id = trace.thread_id
        parent = trace.parent
        self._cache[thread_id] = parent

    def drop_trace(self, trace):
        """Drops the specified trace, validating that it is
        actually saved away under the current executing thread.

        """

        if hasattr(trace, '_task'):
            delattr(trace, '_task')

        thread_id = trace.thread_id

        if thread_id not in self._cache:
            _logger.error('Runtime instrumentation error. Attempt to '
                    'drop the trace but where none is active. '
                    'Report this issue to New Relic support.\n%s',
                    ''.join(traceback.format_stack()[:-1]))

            raise RuntimeError('no active trace')

        current = self._cache.get(thread_id)

        if trace is not current:
            _logger.error('Runtime instrumentation error. Attempt to '
                    'drop the trace when it is not the current '
                    'trace. Report this issue to New Relic support.\n%s',
                    ''.join(traceback.format_stack()[:-1]))

            raise RuntimeError('not the current trace')

        del self._cache[thread_id]
        trace._greenlet = None

    def record_io_loop_wait(self, start_time, end_time):
        transaction = self.current_transaction()
        if not transaction:
            return

        duration = end_time - start_time

        if duration < transaction.settings.io_loop_detection_threshold:
            return

        fetch_name = transaction._cached_path.path
        roots = set()

        for trace in self._cache.values():
            # If the trace is on a different transaction and it's asyncio
            if trace.transaction is not transaction and trace._task:
                trace.exclusive -= duration
                roots.add(trace.root)

        for root in roots:
            guid = '%016x' % random.getrandbits(64)
            node = LoopNode(
                fetch_name=fetch_name,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                guid=guid,
            )
            transaction = root.transaction
            transaction._process_node(node)
            root.process_child(node, ignore_exclusive=True)


_trace_cache = TraceCache()


def trace_cache():
    return _trace_cache
