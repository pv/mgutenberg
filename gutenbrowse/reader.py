"""
Simple book reader

"""
import os

from ui import *
from model_text import EbookText

class ReaderWindow(object):
    def __init__(self, app, textbuffer, title):
        self.app = app
        self.textbuffer = textbuffer
        self.title = title

        self._construct()
        self.widget.connect("destroy", self.on_destroy)

    def on_destroy(self, ev):
        self.app.readers.remove(self)

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

        self.textview = TextView()
        self.textview.set_buffer(self.textbuffer)
        self.textview.set_properties(
            cursor_visible=False,
            editable=False,
            justification=gtk.JUSTIFY_FILL,
            left_margin=20,
            right_margin=20,
            indent=50,
            wrap_mode=gtk.WRAP_WORD
            )
        scroll.add(self.textview)

    def show_all(self):
        self.widget.show_all()

def run(app, filename):
    title = os.path.splitext(os.path.basename(filename))[0]
    textbuffer = EbookText(filename)
    reader = ReaderWindow(app, textbuffer, title)
    reader.show_all()
    return reader
