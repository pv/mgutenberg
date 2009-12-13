"""
GUI threading helpers
"""
import threading
import time
import Queue

try:
    import glib
except ImportError:
    import gobject as glib

__all__ = ['run_in_gui_thread', 'run_later_in_gui_thread',
           'assert_gui_thread', 'start_thread', 'run_in_background',
           'SingleRunner']

def run_in_gui_thread(func, *a, **kw):
    """Run the function in the GUI thread next time when the GUI is idle."""
    def timer():
        func(*a, **kw)
        return False
    glib.idle_add(timer)
    return None

def run_later_in_gui_thread(delay, func, *a, **kw):
    """Run the function in the GUI thread, after a delay"""
    def timer():
        func(*a, **kw)
        return False
    glib.timeout_add(delay, timer)
    return None

def assert_gui_thread(func):
    """Assert that this function is ran in the GUI thread. [decorator]"""
    if not __debug__: return func
    def _wrapper(*a, **kw):
        assert threading.currentThread() == threading.enumerate()[0], \
               (func, threading.currentThread(), threading.enumerate())
        return func(*a, **kw)
    _wrapper.__name__ = func.__name__
    return _wrapper

def start_thread(func, *a):
    threading.Thread(target=func, args=a).start()

def run_in_background(func, *a, **kw):
    """
    Run func in background and call callback after it completes.

    Callback is called with return value or, if exception was raised,
    the exception as an argument.
    """
    callback = kw.pop('callback')
    def runner():
        try:
            result = func(*a, **kw)
        except Exception, e:
            result = e
        run_in_gui_thread(callback, result)
    start_thread(runner)

class SingleRunner(object):
    """
    Run a function in GUI thread, but if multiple calls are set up,
    run only the latest one.

    Useful for tasks that need to be run only once.

    """

    def __init__(self, max_delay=None):
        self.scheduled_id = 0
        self.first_event = None
        self.max_delay = max_delay
        if max_delay is not None:
            self.max_delay /= 1000.

    def _run_func(self, run_id, func, *a, **kw):
        ok = (run_id >= self.scheduled_id)
        if self.max_delay is not None and self.first_event is not None:
            ok = ok | (time.time() > self.first_event + self.max_delay)
        if ok:
            if self.max_delay is not None:
                if run_id < self.scheduled_id:
                    self.first_event = time.time()
                else:
                    self.first_event = None
            return func(*a, **kw)

    def run_in_gui_thread(self, func, *a, **kw):
        self.scheduled_id += 1
        if self.max_delay is not None and self.first_event is None:
            self.first_event = time.time()
        run_in_gui_thread(self._run_func, self.scheduled_id, func, *a, **kw)

    def run_later_in_gui_thread(self, delay, func, *a, **kw):
        self.scheduled_id += 1
        if self.max_delay is not None and self.first_event is None:
            self.first_event = time.time()
        run_later_in_gui_thread(delay, self._run_func, self.scheduled_id,
                                func, *a, **kw)
