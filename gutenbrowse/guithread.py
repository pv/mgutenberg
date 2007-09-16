"""
GUI threading helpers
"""
import threading, Queue
import gobject

def run_in_gui_thread(func, *a, **kw):
    """Run the function in the GUI thread next time when the GUI is idle."""
    def timer():
        func(*a, **kw)
        return False
    gobject.idle_add(timer)
    return None

def run_later_in_gui_thread(delay, func, *a, **kw):
    """Run the function in the GUI thread, after a delay"""
    def timer():
        func(*a, **kw)
        return False
    gobject.timeout_add(delay, timer)
    return None

def assert_gui_thread(func):
    """Assert that this function is ran in the GUI thread. [decorator]"""
    if not __debug__: return func
    def _wrapper(*a, **kw):
        assert threading.currentThread() == threading.enumerate()[0], \
               (func, threading.currentThread(), threading.enumerate())
        return func(*a, **kw)
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
    def __init__(self):
        self.scheduled_id = 0

    def run_func(self, run_id, func, *a, **kw):
        if run_id >= self.scheduled_id:
            return func(*a, **kw)

    def run_in_gui_thread(self, func, *a, **kw):
        self.scheduled_id += 1
        run_in_gui_thread(self.run_func, self.scheduled_id, func, *a, **kw)

    def run_later_in_gui_thread(self, delay, func, *a, **kw):
        self.scheduled_id += 1
        run_later_in_gui_thread(delay, self.run_func, self.scheduled_id,
                                func, *a, **kw)
