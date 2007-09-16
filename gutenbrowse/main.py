#!/usr/bin/env python
import pygtk
pygtk.require('2.0')
import gtk, gobject, subprocess, os, optparse, urllib

from model import *
from gettext import gettext as _

try:
    import hildon
    MAEMO = True
    AppBase = hildon.Program
    Window = hildon.Window
except ImportError:
    MAEMO = False
    AppBase = object
    Window = gtk.Window

class GutenbrowseApp(AppBase):
    def __init__(self, base_directory):
        AppBase.__init__(self)

        self.base_directory = base_directory
        self.ebook_list = EbookList(base_directory)
        self.window = MainWindow(self)

        if MAEMO:
            self.add_window(self.window.widget)

        # Refresh ebook list
        
        def done_cb():
            end_notify()
            self.window.ebook_list.widget_tree.set_model(self.ebook_list)

        end_notify = self.show_notify(self.window.widget,
                                      _("Finding books..."))
        self.window.ebook_list.widget_tree.set_model(None)
        self.ebook_list.refresh(callback=done_cb)
                
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

    def run(self):
        self.window.show_all()
        
        gtk.gdk.threads_init()
        gtk.main()

class EbookListWidget(object):
    def __init__(self, app):
        self.app = app
        self.store = app.ebook_list
        self._construct()
        
        self.widget_tree.connect("row-activated", self.on_activated)
        self.widget_tree.connect("map-event", self.on_map_event)
        
    def on_activated(self, treeview, it, column):
        cmd = ['FBReader', self.store[it][3]]
        os.spawnvp(os.P_NOWAIT, cmd[0], cmd)

    def on_map_event(self, widget, ev):
        run_later_in_gui_thread(500,
                                self.widget_tree.columns_autosize)

    # ---

    def _construct(self):
        self.widget_scroll = gtk.ScrolledWindow()
        self.widget_tree = gtk.TreeView(self.store)

        self.widget_scroll.set_policy(gtk.POLICY_AUTOMATIC,
                                      gtk.POLICY_ALWAYS)
        self.widget_scroll.add(self.widget_tree)

        self.widget_tree.set_enable_search(True)
        self.widget_tree.set_headers_visible(True)
        
        author_cell = gtk.CellRendererText()
        author_col = gtk.TreeViewColumn(_('Author'), author_cell, text=0)
        
        title_cell = gtk.CellRendererText()
        title_col = gtk.TreeViewColumn(_('Title'), title_cell, text=1)
        
        lang_cell = gtk.CellRendererText()
        lang_col = gtk.TreeViewColumn(_('Language'), lang_cell, text=2)
        
        for j, col in enumerate([author_col, title_col, lang_col]):
            col.set_sort_column_id(j)
            col.set_resizable(True)
            
            # speed up large lists...
            col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            col.set_fixed_width(200)
            self.widget_tree.append_column(col)
        
        self.widget = self.widget_scroll
        
        # optimizations for large lists
        self.widget_tree.set_fixed_height_mode(True)

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
            def done_cb(path):
                notify_cb()
                self.app.ebook_list.add(
                    self.info.author,
                    self.info.title,
                    self.info.language,
                    path)
            
            res = self.info.download(sel, self.app.base_directory,
                                     callback=done_cb)
            if not res:
                print "FILE_ALREADY_EXISTS"
                # XXX: NotImplemented
            else:
                notify_cb = self.app.show_notify(self.widget,
                                                 _("Downloading..."))
                self.widget.destroy()

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
            (_("Title:"), self.info.title),
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
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
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

        # Action buttons
        self.down_button = gtk.Button(stock=gtk.STOCK_SAVE)
        self.cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)

        hbox.pack_start(self.down_button)
        hbox.pack_start(self.cancel_button)

class GutenbergSearchWidget(object):
    def __init__(self, app):
        self.app = app
        self.results = GutenbergSearchList()
        self._construct()

        # XXX: debug insert
        self.results.add("Nietzsche","Thus spake Zarathustra","English",
                         "Audio book", 19634)

        self.search_button.connect("clicked", self.on_search_clicked)
        self.widget_tree.connect("row-activated", self.on_activated)

    def on_search_clicked(self, btn):
        done_cb = self.app.show_notify(self.widget, _("Searching..."))
        self.results.new_search(
            self.search_author.get_text(),
            self.search_title.get_text(),
            callback=done_cb)

    def on_activated(self, tree, it, column):
        entry = self.results[it]

        if entry[4] == NEXT_ID:
            done_cb = self.app.show_notify(self.widget, _("Searching..."))
            self.results.next_page(callback=done_cb)
            return
        elif entry[4] == PREV_ID:
            done_cb = self.app.show_notify(self.widget, _("Searching..."))
            self.results.prev_page(callback=done_cb)
            return
        else:
            notify_cb = self.app.show_notify(self.widget,
                                             _("Fetching information..."))
            def on_finish():
                notify_cb()
                w = GutenbergDownloadWindow(self.app, info)
                w.show()
            info = self.results.get_downloads(it, callback=on_finish)

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
            lbl.set_alignment(0.5, 0.5)
            tbl.attach(lbl, 0, 1, j, j+1, xoptions=gtk.FILL)
            tbl.attach(b, 1, 2, j, j+1, xoptions=gtk.FILL|gtk.EXPAND)
        
        box.pack_start(tbl, fill=False, expand=False)
        box.pack_start(self.search_button, fill=False, expand=False)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
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

class MainWindow(object):
    def __init__(self, app):
        self.app = app

        self.ebook_list = EbookListWidget(self.app)
        self.gutenberg_search = GutenbergSearchWidget(self.app)

        self._construct()
        self.widget.connect("destroy", self.on_destroy)

    def show_all(self):
        self.widget.show_all()

    def _construct(self):
        # Window
        self.widget = Window()
        self.widget.set_title("Gutenbrowse")

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

        # Menu

        # Ebook context menu

        # Status bar (non-Maemo)
        if not MAEMO:
            self.statusbar = gtk.Statusbar()
            vbox.pack_start(self.statusbar, expand=False, fill=True)

    #-- Signals

    def on_destroy(self, ev):
        gtk.main_quit()

def main():
    p = optparse.OptionParser()
    options, args = p.parse_args()
    
    app = GutenbrowseApp(args[0])
    app.run()
