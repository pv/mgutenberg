"""
Simple book reader

"""
import os
import time
import math

from ui import *
from model_text import EbookText

class ReaderWindow(object):
    def __init__(self, app, textbuffer, filename):
        self.app = app
        self.textbuffer = textbuffer

        self.filename = filename
        self.title = os.path.splitext(os.path.basename(filename))[0]

        self._update_info_schedule = SingleRunner(max_delay=1000)
        self._page_height = None

        self._last_size = None
        self._button_press = None
        self._destroyed = False

        # Get saved position, before creating the window
        pos = self.app.config['positions'].get(filename, 0)

        # Create window and connect signals
        self._construct()
        self.widget.connect("destroy", self.on_destroy)
        self.textscroll.get_vadjustment().connect("value-changed",
                                                  self.on_scrolled)

        # Click events
        self.textscroll.add_events(gtk.gdk.BUTTON_RELEASE_MASK
                                   | gtk.gdk.BUTTON_PRESS_MASK)
        self.textscroll.connect("button-press-event",
                                self.button_press_event)
        self.textscroll.connect("button-release-event",
                                self.button_release_event)

        # Scroll to saved position
        it = textbuffer.get_iter_at_offset(pos)
        self.mark = textbuffer.create_mark("pos", it)
        self.textview.scroll_to_mark(self.mark, 0, use_align=True, yalign=0)

    def on_destroy(self, ev):
        self._destroyed = True
        try:
            self.app.readers.remove(self)
        except ValueError:
            pass

    @assert_gui_thread
    def _construct(self):
        self.widget = StackableWindow()
        self.widget.set_title("%s - Gutenbrowse" % self.title)

        box = gtk.VBox()
        self.widget.add(box)

        if MAEMO:
            scroll = hildon.PannableArea()
        else:
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        box.pack_start(scroll, fill=True, expand=True)

        self.textscroll = scroll
        self.textview = TextView()
        self.textview.set_buffer(self.textbuffer)
        self.textview.set_properties(
            cursor_visible=False,
            editable=False,
            justification=gtk.JUSTIFY_FILL,
            left_margin=20,
            right_margin=20,
            indent=40,
            wrap_mode=gtk.WRAP_WORD
            )
        scroll.add(self.textview)

        hbox = gtk.HBox()
        box.pack_end(hbox, fill=True, expand=False)

        self.info = gtk.Label()
        self.info.set_alignment(0.95, 0.5)
        hbox.pack_end(self.info, fill=True, expand=False)

    def _update_info(self):
        if self._destroyed:
            return

        size = self.textview.size_request()
        if size != self._last_size:
            # Wait until size converges -- e.g. when textview is still loading
            self._last_size = size
            self._update_info_schedule.run_later_in_gui_thread(
                1000, self._update_info)
            return

        rect = self.textview.get_visible_rect()

        cpage = round(1 + rect.y / rect.height)
        npages = round(1 + size[1] / rect.height)
        self.info.set_text('%d / %d' % (cpage, npages))

        it = self.textview.get_iter_at_location(rect.x, rect.y)

        # Save position
        self.app.config['positions'][self.filename] = it.get_offset()
        print self.filename, self.app.config['positions'][self.filename]

    def on_scrolled(self, adj):
        self._update_info_schedule.run_later_in_gui_thread(
            100, self._update_info)

    def button_press_event(self, widget, event):
        self._button_press = (event.x, event.y, time.time())

    def button_release_event(self, widget, event):
        press = self._button_press
        self._button_press = None

        # Require a tap, not panning etc.
        if not press:
            return False
        if math.hypot(press[0]-event.x, press[1]-event.y) > 50:
            return False
        if time.time() - press[2] > 0.5:
            return False

        # Check direction, and pan
        w, h = self.widget.size_request()
        if event.y > 2*h/3:
            self.textview.emit("move-viewport", gtk.SCROLL_PAGES, 1)
        elif event.y < h/3:
            self.textview.emit("move-viewport", gtk.SCROLL_PAGES, -1)
        else:
            return False
        return True

    def show_all(self):
        self.widget.show_all()
        self._update_info_schedule.run_later_in_gui_thread(
            100, self._update_info)
        
def run(app, filename):
    notify_cb = app.show_notify(app.window.widget, _("Loading..."))

    def load_buffer_cb(textbuffer):
        notify_cb()
        title = os.path.splitext(os.path.basename(filename))[0]
        if textbuffer.error:
            msg = _("<b>Loading failed:</b>")
            dlg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                    buttons=gtk.BUTTONS_OK)
            dlg.set_markup(msg)
            dlg.format_secondary_text(title + "\n" + textbuffer.error)
            dlg.connect("response", lambda obj, ev: dlg.destroy())
            dlg.run()
            return None
        else:
            reader = ReaderWindow(app, textbuffer, filename)
            reader.show_all()
            return reader

    run_in_background(EbookText, filename, callback=load_buffer_cb)
