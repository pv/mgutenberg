"""
Simple book reader

"""
import os

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

        # Get saved position, before creating the window
        pos = self.app.config['positions'].get(filename, 0)

        # Create window and connect signals
        self._construct()
        self.widget.connect("destroy", self.on_destroy)
        self.textscroll.get_vadjustment().connect("value-changed",
                                                  self.on_scrolled)

        # Scroll to saved position
        it = textbuffer.get_iter_at_offset(pos)
        self.mark = textbuffer.create_mark("pos", it)
        self.textview.scroll_to_mark(self.mark, 0, use_align=True, yalign=0)

    def on_destroy(self, ev):
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

        self.info = gtk.Label()
        self.info.set_alignment(0.95, 0.5)
        box.pack_end(self.info, fill=True, expand=False)

    def _update_info(self):
        size = self.textview.size_request()

        if size != self._last_size:
            # Wait until size converges -- e.g. when textview is still loading
            self._last_size = size
            self._update_info_schedule.run_later_in_gui_thread(
                1000, self._update_info)
            return

        rect = self.textview.get_visible_rect()

        perc = round(rect.y * 100.0 / max(1.0,max(rect.y, size[1]-rect.height)))
        cpage = round(1 + rect.y / rect.height)
        npages = round(1 + size[1] / rect.height)

        self.info.set_text('%d / %d, %d %%' % (cpage, npages, perc))

        # Save position
        it = self.textview.get_iter_at_location(rect.x, rect.y)
        self.app.config['positions'][self.filename] = it.get_offset()

    def on_scrolled(self, adj):
        self._update_info_schedule.run_later_in_gui_thread(
            100, self._update_info)

    def show_all(self):
        self.widget.show_all()
        self._update_info_schedule.run_later_in_gui_thread(
            100, self._update_info)
        
def run(app, filename):
    textbuffer = EbookText(filename)
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
