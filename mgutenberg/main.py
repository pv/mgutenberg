#!/usr/bin/env python
import subprocess
import os
import optparse
import urllib

from ui import *
from model import *
import reader

CONFIG_SCHEMA = {
    'search_dirs': (list, str),
    'save_dir': str,
    'positions': (dict, int),
    'inverse_colors': bool,
    'portrait': bool,
}

def main():
    p = optparse.OptionParser()
    options, args = p.parse_args()

    # Config & defaults
    config = Config(CONFIG_SCHEMA)
    try:
        config.load()
    except IOError:
        pass

    if MAEMO:
        sdirs = [os.path.expanduser("~/MyDocs/.documents/Books")]
    else:
        sdirs = [os.path.join(os.path.expanduser("~"), "Desktop", "Books")]
    config.setdefault('search_dirs', sdirs)
    config.setdefault('save_dir', sdirs[0])
    config.setdefault('positions', {})
    config.setdefault('inverse_colors', False)
    config.setdefault('portrait', False)

    # Run
    app = MGutenbergApp(config)
    app.run()


# XXX: revise those deeply nested callbacks; try to reduce nesting of code

class MGutenbergApp(AppBase):
    def __init__(self, config):
        AppBase.__init__(self)
        
        self.config = config
        self.ebook_list = EbookList(config['search_dirs'])
        self.window = MainWindow(self)
        self.readers = []

        if MAEMO:
            self.add_window(self.window.widget)

    def error_message(self, text, moreinfo=""):
        dlg = gtk.MessageDialog(self.window.widget,
                                type=gtk.MESSAGE_ERROR,
                                buttons=gtk.BUTTONS_OK)
        dlg.set_markup("<b>%s</b>" % text)
        dlg.format_secondary_text(str(moreinfo))
        def response(dlg, response_id):
            dlg.destroy()
        dlg.connect("response", response)
        dlg.show()
    
    def show_notify(self, widget, text):
        if MAEMO:
            banner = hildon.hildon_banner_show_animation(
                widget, "qgn_indi_pball_a", text)
            banner.show()
            return banner.destroy
        else:
            self.window.statusbar.push(0, text)
            def finish():
                self.window.statusbar.pop(0)
            return finish

    def show_notify_working(self, widget):
        if MAEMO:
            hildon.hildon_gtk_window_set_progress_indicator(widget, 1)
            def cb():
                hildon.hildon_gtk_window_set_progress_indicator(widget, 0)
            return cb
        else:
            return self.show_notify(widget, _("Working..."))

    def start_reader(self, filename):
        reader.run(self, filename)

    def run(self):
        self.window.show_all()

        # Refresh ebook list

        def done_cb(r):
            end_notify()
            self.window.ebook_list.thaw()
            if isinstance(r, Exception):
                self.app.error_message(_("Error refreshing book list"), r)

        end_notify = self.show_notify(self.window.widget,
                                      _("Looking for books..."))
        self.window.ebook_list.freeze()
        self.ebook_list.refresh(callback=done_cb)

        # Start

        gtk.gdk.threads_init()
        gtk.main()

    def quit(self):
        self.config.save()
        gtk.main_quit()

class MainWindow(object):
    if not MAEMO:
        UI_XMLS = ["""
        <ui>
          <menubar name="menu_bar">
            <menu name="file" action="file">
              <menuitem action="open" />
              <separator name="quit_sep" />
              <menuitem name="quit" action="quit" />
            </menu>
          </menubar>
        </ui>
        """]

    def __init__(self, app):
        self.app = app

        self.ebook_list = EbookListWidget(self.app)
        self.gutenberg_search = GutenbergSearchWidget(self.app)

        self._construct()
        self.widget.connect("destroy", self.on_destroy)

    def show_all(self):
        self.widget.show_all()

        if self.menu is not None:
            self.widget.set_app_menu(self.menu)
            self.menu.show_all()

    # ---

    def on_action_open(self, action):
        dlg = FileChooserDialog(parent=self.widget,
                                buttons=(gtk.STOCK_CANCEL,
                                         gtk.RESPONSE_CANCEL,
                                         gtk.STOCK_OPEN,
                                         gtk.RESPONSE_ACCEPT),
                                action=gtk.FILE_CHOOSER_ACTION_OPEN)

        def response(dlg, response_id):
            if response_id == gtk.RESPONSE_ACCEPT:
                fn = dlg.get_filename()
                if fn:
                    self.app.start_reader(fn)
            dlg.destroy()

        dlg.connect("response", response)
        dlg.show()

    def on_action_quit(self, action):
        self.app.quit()

    def on_destroy(self, ev):
        self.app.quit()

    # ---

    def _construct(self):
        # Window
        self.widget = StackableWindow()
        self.widget.set_title("MGutenberg")

        vbox = gtk.VBox()
        self.widget.add(vbox)

        # Notebook packing
        self.notebook = gtk.Notebook()
        self.notebook.set_border_width(5)
        self.notebook.set_show_border(False)
        vbox.pack_start(self.notebook)

        # Local ebooks tab
        page = gtk.VBox()
        page.pack_end(self.ebook_list.widget, expand=True, fill=True)
        self.notebook.append_page(page, gtk.Label(_("Books")))

        # Gutenberg tab
        page = gtk.VBox()
        page.pack_end(self.gutenberg_search.widget, expand=True, fill=True)
        self.notebook.append_page(page, gtk.Label(_("Gutenberg")))

        self.gutenberg_search.search_button.grab_default()

        if MAEMO:
            # Tabs are changed from menu
            self.notebook.set_show_tabs(False)

        # Menu &c
        if MAEMO:
            self._construct_menu_maemo()
        else:
            self._construct_menu(vbox)

        # Ebook context menu

        # XXX: implement

        # Status bar (non-Maemo)
        if not MAEMO:
            self.statusbar = gtk.Statusbar()
            vbox.pack_start(self.statusbar, expand=False, fill=True)

    def _construct_menu(self, vbox):
        actiongroup = gtk.ActionGroup('actiongroup')
        actiongroup.add_actions([
            ('file', None, _("_File")),
            ('open', None, _("_Open..."), None,
             None, self.on_action_open),
            ('quit', gtk.STOCK_QUIT, _("_Quit"), None,
             None, self.on_action_quit)
        ])
        
        self.uim = gtk.UIManager()
        self.uim.insert_action_group(actiongroup, 0)
        for xml in self.UI_XMLS:
            self.uim.add_ui_from_string(xml)

        menu_bar = self.uim.get_widget('/menu_bar')
        self.widget.add_accel_group(self.uim.get_accel_group())
        vbox.pack_start(menu_bar, fill=True, expand=False)
        vbox.reorder_child(menu_bar, 0)
        self.menu = None

    # -- Maemo-specific:

    def on_book_button_click(self, widget):
        self.notebook.set_current_page(0)
        self.on_notebook_switch_page(None, None, 0)

    def on_gutenberg_button_click(self, widget):
        self.notebook.set_current_page(1)
        self.on_notebook_switch_page(None, None, 1)

    def on_notebook_switch_page(self, notebook, page, page_num):
        self.book_button.handler_block_by_func(self.on_book_button_click)
        self.gutenberg_button.handler_block_by_func(
            self.on_gutenberg_button_click)

        self.book_button.set_active(page_num == 0)
        self.gutenberg_button.set_active(page_num == 1)

        self.book_button.handler_unblock_by_func(self.on_book_button_click)
        self.gutenberg_button.handler_unblock_by_func(
            self.on_gutenberg_button_click)

    def on_open_file(self, widget):
        m = hildon.FileSystemModel()
        dlg = FileChooserDialog(self.widget, gtk.FILE_CHOOSER_ACTION_OPEN, m)
        dlg.set_current_folder_uri("file://" + self.app.config['save_dir'])

        def response(dlg, response_id):
            fn = dlg.get_filename()
            if fn:
                self.app.start_reader(fn)
            dlg.destroy()

        dlg.connect("response", response)
        dlg.show()

    def _construct_menu_maemo(self):
        menu = hildon.AppMenu()

        # Filter buttons
        self.gutenberg_button = gtk.ToggleButton(label=_("Project Gutenberg"))
        self.book_button = gtk.ToggleButton(label=_("Local books"))

        self.gutenberg_button.connect("toggled", self.on_gutenberg_button_click)
        self.book_button.connect("toggled", self.on_book_button_click)

        self.notebook.connect("switch_page",
                              self.on_notebook_switch_page)

        menu.add_filter(self.gutenberg_button)
        menu.add_filter(self.book_button)

        open_file_button = gtk.Button(label=_("Open file"))
        open_file_button.connect("clicked", self.on_open_file)
        menu.append(open_file_button)

        # Select buttons
        self.menu = menu

class EbookListWidget(object):
    UI_XMLS = ["""
    <ui>
      <popup name="popup">
        <menuitem action="read" />
        <menuitem action="delete" />
      </menubar>
    </ui>
    """]

    def __init__(self, app):
        self.app = app
        self.filter_text = ''

        self.store = app.ebook_list
        self.filter = None
        self.filtered_store = None
        
        self._construct()

        self.filter_runner = SingleRunner()

        self.widget_tree.connect("row-activated", self.on_activated)
        self.widget_tree.connect("map-event", self.on_map_event)
        self.filter_entry.connect("changed", self.on_filter_changed)

        # Click events
        self.widget_tree.add_events(gtk.gdk.BUTTON_RELEASE_MASK
                                    | gtk.gdk.BUTTON_PRESS_MASK)
        self.widget_tree.connect("button-press-event",
                                 self.on_button_press_event)
        self.widget_tree.connect("button-release-event",
                                 self.on_button_release_event)
        self._active_item = None

    def freeze(self):
        self.widget_tree.set_model(None)
        
    def thaw(self):
        self.widget_tree.set_model(self.store)

    # ---

    def _show_context_menu(self, x, y, time, button):
        if self._active_item is not False:
            return
        pthinfo = self.widget_tree.get_path_at_pos(int(x), int(y))
        if pthinfo is not None:
            path, col, cellx, celly = pthinfo
            self._active_item = path
            self.widget_tree.grab_focus()
            self.widget_tree.set_cursor(path, col, 0)
            self.menu.popup(None, None, None, button, time)

    def on_button_press_event(self, widget, event):
        self._active_item = False
        if MAEMO:
            run_later_in_gui_thread(500, self._show_context_menu,
                                    event.x, event.y, event.time, event.button)
        else:
            if event.button == 3:
                self._show_context_menu(event.x, event.y, event.time,
                                        event.button)

    def on_button_release_event(self, widget, event):
        self._active_item = None

    def on_menu_read(self, widget):
        model = self.widget_tree.get_model()
        try:
            entry = model[model.get_iter(self._active_item)]
            self.app.start_reader(entry[3])
        except ValueError:
            pass
        self._active_item = None

    def on_menu_delete(self, widget):
        model = self.widget_tree.get_model()
        try:
            it = model.get_iter(self._active_item)
            entry = model[it]
            self._active_item = None

            def response(widget, response_id):
                if response_id == gtk.RESPONSE_YES:
                    model.delete_file(it)
                dlg.destroy()
            if MAEMO:
                dlg = hildon.Note("confirmation",
                                  self.app.window.widget,
                                  "Delete file\n%s"%os.path.basename(entry[3]))
            else:
                dlg = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
                                        buttons=gtk.BUTTONS_YES_NO)
                dlg.set_markup("<b>Delete file?</b>")
                dlg.format_secondary_text(os.path.basename(entry[3]))
            dlg.connect("response", response)
            dlg.show()
        except ValueError:
            pass

    def on_activated(self, treeview, it, column):
        entry = treeview.get_model()[it]
        self.app.start_reader(entry[3])

    def on_map_event(self, widget, ev):
        run_later_in_gui_thread(500,
                                self.widget_tree.columns_autosize)

    def on_filter_changed(self, w):
        def do_refilter():
            if len(''.join(self.filter_text)) <= 2:
                self.filter = None
                self.filtered_store = None
                if self.widget_tree.get_model() is not self.store:
                    self.widget_tree.set_model(self.store)
            else:
                if not self.filter:
                    self.filter = self.store.filter_new()
                    self.filtered_store = gtk.TreeModelSort(self.filter)
                    self.filter.set_visible_func(self.filter_func)
                
                self.filter.refilter()
                if self.widget_tree.get_model() is not self.filtered_store:
                    self.widget_tree.set_model(self.filtered_store)
        
        self.filter_text = self.filter_entry.get_text().lower().strip().split()
        
        delay = 1000 if MAEMO else 500
        self.filter_runner.run_later_in_gui_thread(delay, do_refilter)

    def filter_func(self, model, it, data=None):
        if not self.filter_text: return True
        entry = model[it]
        try:
            raw = ''.join([entry[0], entry[1], entry[2]]).lower()
        except TypeError:
            return True
        return all(x in raw for x in self.filter_text)

    # ---

    def _construct(self):
        box = gtk.VBox()
        self.widget = box

        # Filter entry
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Search:")), fill=False, expand=False)
        self.filter_entry = gtk.Entry()
        hbox.pack_start(self.filter_entry, fill=True, expand=True)
        box.pack_end(hbox, fill=True, expand=False)

        # Tree
        if MAEMO:
            scroll = hildon.PannableArea()
        else:
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)

        box.pack_start(scroll, fill=True, expand=True)

        self.widget_tree = gtk.TreeView(self.store)
        scroll.add(self.widget_tree)

        self.widget_tree.set_enable_search(True)
        if MAEMO:
            self.widget_tree.set_headers_visible(False)
        else:
            self.widget_tree.set_headers_visible(True)
        
        author_cell = gtk.CellRendererText()
        author_col = gtk.TreeViewColumn(_('Author'), author_cell, text=0)
        
        title_cell = gtk.CellRendererText()
        title_col = gtk.TreeViewColumn(_('Title'), title_cell, text=1)
        
        lang_cell = gtk.CellRendererText()
        lang_col = gtk.TreeViewColumn(_('Language'), lang_cell, text=2)

        widths = [300, 400, 80]
        for j, col in enumerate([author_col, title_col, lang_col]):
            col.set_sort_column_id(j)
            col.set_resizable(True)
            
            # speed up large lists...
            col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            col.set_fixed_width(widths[j])
            self.widget_tree.append_column(col)

        # optimizations for large lists
        self.widget_tree.set_fixed_height_mode(True)

        # context menu
        self.menu = gtk.Menu()
        read = gtk.MenuItem(_("Read"))
        delete = gtk.MenuItem(_("Delete"))
        self.menu.append(read)
        self.menu.append(delete)
        self.menu.show_all()
        read.connect("activate", self.on_menu_read)
        delete.connect("activate", self.on_menu_delete)
        if MAEMO:
            self.menu.set_name("hildon-context-sensitive-menu")

class GutenbergSearchWidget(object):
    def __init__(self, app):
        self.app = app
        self.results = GutenbergSearchList()
        self._construct()

        self.search_button.connect("clicked", self.on_search_clicked)
        self.widget_tree.connect("row-activated", self.on_activated)

    def on_search_clicked(self, btn):
        def done_cb(r):
            notify_cb()
            if isinstance(r, Exception):
                self.app.error_message(_("Error in fetching search results"),
                                       r)
        notify_cb = self.app.show_notify(self.widget, _("Searching..."))
        self.results.new_search(
            self.search_author.get_text(),
            self.search_title.get_text(),
            callback=done_cb)

    def on_activated(self, tree, it, column):
        entry = self.results[it]

        def done_cb(r):
            notify_cb()
            if isinstance(r, Exception):
                self.app.error_message(_("Error in fetching search results"),
                                       r)

        if entry[4] == NEXT_ID:
            notify_cb = self.app.show_notify(self.widget, _("Searching..."))
            self.results.next_page(callback=done_cb)
            return
        elif entry[4] == PREV_ID:
            notify_cb = self.app.show_notify(self.widget, _("Searching..."))
            self.results.prev_page(callback=done_cb)
            return
        else:
            notify_cb = self.app.show_notify(self.widget,
                                             _("Fetching information..."))
            
            def on_finish(info):
                notify_cb()
                if isinstance(info, Exception):
                    self.app.error_message(
                        _("Error in fetching ebook information"), info)
                else:
                    w = GutenbergDownloadWindow(self.app, info)
                    w.show()
            
            self.results.get_downloads(it, callback=on_finish)

    # ---

    def _construct(self):
        box = gtk.VBox()
        box.set_spacing(5)
        self.widget = box

        self.search_title = gtk.Entry()
        self.search_author = gtk.Entry()
        self.search_button = gtk.Button(_("Search"))

        self.search_title.set_activates_default(True)
        self.search_author.set_activates_default(True)
        self.search_button.set_flags(gtk.CAN_DEFAULT)

        tbl = gtk.Table(rows=3, columns=2)

        entries = [(_("Author:"), self.search_author),
                   (_("Title:"), self.search_title),
                   ]
        for j, (a, b) in enumerate(entries):
            lbl = gtk.Label(a)
            lbl.set_alignment(0., 0.5)
            tbl.attach(lbl, 0, 1, j, j+1, xoptions=gtk.FILL)
            tbl.attach(b, 1, 2, j, j+1, xoptions=gtk.FILL|gtk.EXPAND)
        
        if MAEMO:
            scroll = hildon.PannableArea()
            scroll.set_properties(
                mov_mode=hildon.MOVEMENT_MODE_BOTH
                )
        else:
            scroll = gtk.ScrolledWindow()
            scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)

        hbox = gtk.HBox()
        hbox.pack_start(tbl, fill=True, expand=True)
        hbox.pack_start(self.search_button, fill=False, expand=False)
        box.pack_start(hbox, fill=False, expand=False)
        box.pack_start(scroll, fill=True, expand=True)

        self.widget_tree = gtk.TreeView(self.results)
        self.widget_tree.set_enable_search(True)

        scroll.add(self.widget_tree)

        author_cell = gtk.CellRendererText()
        author_col = gtk.TreeViewColumn(_('Author'), author_cell, text=0)
        author_col.set_sort_column_id(0)
        author_col.set_resizable(True)

        title_cell = gtk.CellRendererText()
        title_col = gtk.TreeViewColumn(_('Title'), title_cell, text=1)
        title_col.set_sort_column_id(1)
        title_col.set_resizable(True)

        lang_cell = gtk.CellRendererText()
        lang_col = gtk.TreeViewColumn(_('Language'), lang_cell, text=2)
        lang_col.set_sort_column_id(2)
        lang_col.set_resizable(True)

        cat_cell = gtk.CellRendererText()
        cat_col = gtk.TreeViewColumn(_('Category'), lang_cell, text=3)
        cat_col.set_sort_column_id(3)
        cat_col.set_resizable(True)

        self.widget_tree.append_column(author_col)
        self.widget_tree.append_column(title_col)
        self.widget_tree.append_column(lang_col)
        self.widget_tree.append_column(cat_col)

class GutenbergDownloadWindow(object):
    def __init__(self, app, info):
        self.app = app
        self.info = info
        self._construct()

        self.cancel_button.connect("clicked", self.on_cancel_clicked)
        self.down_button.connect("clicked", self.on_down_clicked)

        sel = self.down_list.get_selection()
        sel.set_mode(gtk.SELECTION_SINGLE)
        sel.connect("changed", self.on_selection_changed)
        self.down_button.set_sensitive(False)

    def on_down_clicked(self, w):
        sel = self.down_list.get_selection().get_selected()[1]
        if sel:
            def done_cb(path, notify_cb):
                notify_cb()
                if isinstance(path, Exception):
                    self.app.error_message(
                        _("Error in dowloading the file"), path)
                else:
                    self.app.ebook_list.add(
                        self.info.author,
                        self.info.title,
                        self.info.language,
                        path)

                    dlg = gtk.MessageDialog(self.app.window.widget)
                    dlg.set_markup("<b>%s</b>" % _("Download finished"))
                    dlg.format_secondary_text(
                        _("Ebook %s by %s is now downloaded. Do "
                          "you want to read it?") % (self.info.title,
                                                     self.info.author))
                    dlg.add_button(_("Read it"), 1)
                    dlg.add_button(gtk.STOCK_CANCEL, 0)
                    def response(dlg, response_id, path):
                        if response_id:
                            self.app.start_reader(path)
                        dlg.destroy()
                    dlg.connect("response", response, path)
                    dlg.show()

            def proceed(selected, overwrite=False):
                self.info.download(selected,
                                   self.app.config['save_dir'],
                                   overwrite=overwrite,
                                   callback=lambda x: done_cb(x, notify_cb))
                # XXX: Download notify doesn't work on Maemo??
                notify_cb = self.app.show_notify(self.widget,
                                                 _("Downloading..."))
                self.widget.destroy()
                                
            try:
                proceed(sel)
            except OverwriteFileException:
                dlg = gtk.MessageDialog(self.app.window.widget)
                dlg.set_markup("<b>%s</b>" % _("Overwrite file?"))
                dlg.format_secondary_text(
                    _("Ebook %s by %s appears already to be on your disk. "
                      "Do you want to overwrite it with a version from "
                      "Project Gutenberg?") % (self.info.title,
                                               self.info.author))
                dlg.add_button(_("Overwrite"), 1)
                dlg.add_button(gtk.STOCK_CANCEL, 0)
                def response(dlg, response_id, selected):
                    if response_id:
                        proceed(selected, overwrite=True)
                    dlg.destroy()
                dlg.connect("response", response, sel)
                dlg.show()

    def on_cancel_clicked(self, w):
        self.widget.destroy()

    def on_selection_changed(self, w):
        sel = self.down_list.get_selection().get_selected()[1]
        if sel:
            self.down_button.set_sensitive(True)
        else:
            self.down_button.set_sensitive(False)
        
    def show(self):
        self.widget.show_all()

    # ---

    def _construct(self):
        self.widget = gtk.Dialog(self.info.title,
                                 parent=self.app.window.widget)

        box = self.widget.vbox
        hbox = self.widget.action_area

        # Info box
        tbl = gtk.Table(rows=4, columns=2)

        infoentries = [
            (_("Etext:"), str(self.info.etext_id)),
            (_("Author:"), self.info.author),
            (_("Language:"), self.info.language),
        ]

        for j, (a, b) in enumerate(infoentries):
            lbl_a = gtk.Label()
            lbl_a.set_markup(u"<b>%s</b>" % a)
            lbl_a.set_alignment(0.0, 0.0)

            lbl_b = gtk.Label(b)
            lbl_b.set_alignment(0.0, 0.0)

            tbl.attach(lbl_a, 0, 1, j, j+1, xoptions=gtk.FILL, xpadding=5)
            tbl.attach(lbl_b, 1, 2, j, j+1, xoptions=gtk.FILL|gtk.EXPAND,
                       xpadding=5)

        box.pack_start(tbl, expand=False, fill=True)

        # Download list
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.down_list = gtk.TreeView(self.info)
        scroll.add(self.down_list)
        box.pack_start(scroll, expand=True, fill=True)

        info_cell = gtk.CellRendererText()
        info_col = gtk.TreeViewColumn(_("Format"), info_cell, text=1)
        info_col.set_sort_column_id(1)

        file_cell = gtk.CellRendererText()
        file_col = gtk.TreeViewColumn(_("File"), file_cell)
        def pretty_filename(treeviewcolumn, cell, model, iter):
            url = model.get_value(iter, 0)
            url = urllib.unquote(url.split('/')[-1])
            cell.set_property('text', url)
        file_col.set_cell_data_func(file_cell, pretty_filename)

        self.down_list.append_column(info_col)
        self.down_list.append_column(file_col)

        self.down_list.set_size_request(300, 400)

        # Action buttons
        self.down_button = gtk.Button(stock=gtk.STOCK_SAVE)
        self.cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)

        hbox.pack_start(self.down_button)
        hbox.pack_start(self.cancel_button)
