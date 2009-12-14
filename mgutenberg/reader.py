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
        self._fullscreen = False

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
        self.widget.set_title("%s - MGutenberg" % self.title)

        if MAEMO:
            hildon.hildon_gtk_window_set_portrait_flags(
                self.widget, hildon.PORTRAIT_MODE_SUPPORT)

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
            left_margin=10,
            right_margin=10,
            indent=40,
            wrap_mode=gtk.WRAP_WORD
            )
        scroll.add(self.textview)

        hbox = gtk.HBox()
        box.pack_end(hbox, fill=True, expand=False)

        self.info = gtk.Label()
        self.info.set_alignment(0.95, 0.5)
        hbox.pack_end(self.info, fill=True, expand=False)

        if MAEMO:
            self._construct_menu_maemo()

    def on_toggle_portrait(self, widget):
        if widget.get_active():
            hildon.hildon_gtk_window_set_portrait_flags(
                self.widget,
                hildon.PORTRAIT_MODE_SUPPORT|hildon.PORTRAIT_MODE_REQUEST)
        else:
            hildon.hildon_gtk_window_set_portrait_flags(
                self.widget, hildon.PORTRAIT_MODE_SUPPORT)
        self.app.config['portrait'] = widget.get_active()

    def on_toggle_inverse_colors(self, widget):
        if widget.get_active():
            gray = gtk.gdk.Color(40000, 40000, 40000)
            black = gtk.gdk.Color(0, 0, 0)
            if MAEMO:
                self.textview.set_name('HildonTextView.hildon-reversed-textview')
            self.textview.modify_text(gtk.STATE_NORMAL, gray)
            self.textview.modify_base(gtk.STATE_NORMAL, black)
            self.info.modify_fg(gtk.STATE_NORMAL, gray)
        else:
            if MAEMO:
                self.textview.set_name('HildonTextView')
            self.textview.modify_text(gtk.STATE_NORMAL, None)
            self.textview.modify_base(gtk.STATE_NORMAL, None)
            self.info.modify_fg(gtk.STATE_NORMAL, None)
        self.app.config['inverse_colors'] = widget.get_active()

    def _construct_menu_maemo(self):
        menu = hildon.AppMenu()

        portrait_button = gtk.ToggleButton(label=_("Portrait"))
        portrait_button.connect("toggled", self.on_toggle_portrait)

        inverse_button = gtk.ToggleButton(label=_("Inverse colors"))
        inverse_button.connect("toggled", self.on_toggle_inverse_colors)

        menu.append(portrait_button)
        menu.append(inverse_button)

        # Select buttons
        self.menu = menu

        # Restore from config
        if self.app.config['inverse_colors']:
            inverse_button.set_active(True)

        if self.app.config['portrait']:
            portrait_button.set_active(True)

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
        if math.hypot(press[0]-event.x, press[1]-event.y) > 70 / 2:
            return False
        if time.time() - press[2] > 0.25:
            return False

        # Unfullscreen check
        w, h = self.widget.size_request()
        if self._fullscreen:
            x_ok = abs(event.x) > 70 or abs(event.y) > 70
        else:
            x_ok = True

        # Check direction, and pan
        if event.y > 2*h/3 and x_ok:
            self._page_down()
        elif event.y < h/3 and x_ok:
            self._page_up()
        else:
            if self._fullscreen:
                self.widget.unfullscreen()
                self.info.show()
                self._fullscreen = False
            else:
                self.widget.fullscreen()
                self.info.hide()
                self._fullscreen = True
        return True

    def _page_down(self):
        """
        Scroll page down, so that *no lines already visible* are shown again.
        """
        rect = self.textview.get_visible_rect()
        it = self.textview.get_iter_at_location(rect.x, rect.y + rect.height)
        self.textview.scroll_to_iter(it, 0, use_align=True, yalign=0)

    def _page_up(self):
        """
        Scroll page up, so that *no lines already visible* are shown again.

        Also, _page_up(); _page_down(); must lead to the same topmost
        full line shown.
        """
        rect = self.textview.get_visible_rect()
        it = self.textview.get_iter_at_location(rect.x, rect.y - 1)
        self.textview.scroll_to_iter(it, 0, use_align=True, yalign=1)

    def show_all(self):
        self.widget.show_all()
        self._update_info_schedule.run_later_in_gui_thread(
            100, self._update_info)

        if self.menu:
            self.widget.set_app_menu(self.menu)
            self.menu.show_all()

def run(app, filename):
    notify_cb = app.show_notify(app.window.widget, _("Loading..."))

    def load_buffer_cb(textbuffer):
        notify_cb()
        error = None

        if isinstance(textbuffer, Exception):
            error = str(textbuffer)
        elif textbuffer.error:
            error = textbuffer.error

        title = os.path.splitext(os.path.basename(filename))[0]
        if error:
            msg = _("<b>Loading failed:</b>")
            dlg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                    buttons=gtk.BUTTONS_OK)
            dlg.set_markup(msg)
            dlg.format_secondary_text(title + "\n" + error)
            dlg.connect("response", lambda obj, ev: dlg.destroy())
            dlg.run()
            return None
        else:
            reader = ReaderWindow(app, textbuffer, filename)
            reader.show_all()
            return reader

    run_in_background(EbookText, filename, callback=load_buffer_cb)
