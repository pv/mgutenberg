#!/usr/bin/env python
import pygtk
pygtk.require('2.0')
import gtk, gobject, subprocess, os, optparse

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

def show_notify(widget, text):
    if MAEMO:
        banner = hildon.hildon_banner_show_animation(widget,
                                                     "qgn_indi_pball_a", text)
        banner.show()
        return banner.destroy
    else:
        # FIXME: Implement
        return lambda: NotImplemented

class GutenbrowseApp(AppBase):
    def __init__(self, base_directory):
        self.ebook_list = EbookList(base_directory)
        self.window = MainWindow(self)

        done_cb = show_notify(self.window.widget, _("Finding books..."))
        self.ebook_list.refresh(callback=done_cb)
                
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

        author_cell = gtk.CellRendererText()
        author_col = gtk.TreeViewColumn(_('Author'), author_cell, text=0)
        
        title_cell = gtk.CellRendererText()
        title_col = gtk.TreeViewColumn(_('Title'), title_cell, text=1)

        lang_cell = gtk.CellRendererText()
        lang_col = gtk.TreeViewColumn(_('Language'), lang_cell, text=2)

        for j, col in enumerate([author_col, title_col, lang_col]):
            col.set_sort_column_id(j)
            col.set_resizable(True)
            col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            col.set_fixed_width(200)
            self.widget_tree.append_column(col)

        self.widget = self.widget_scroll

        # optimizations
        self.widget_tree.set_fixed_height_mode(True)
        self.widget_tree.set_headers_visible(True)

class GutenbergDownloadWindow(object):
    def __init__(self, app):
        self.app = app
        self._construct()

    def _construct(self):
        pass

class GutenbergSearchWidget(object):
    def __init__(self, app):
        self.app = app
        self.results = GutenbergSearchList()
        self._construct()

        self.search_button.connect("clicked", self.on_search_clicked)
        self.widget_tree.connect("row-activated", self.on_activated)

    def on_search_clicked(self, btn):
        done_cb = show_notify(self.widget, _("Searching..."))
        self.results.new_search(
            self.search_author.get_text(),
            self.search_title.get_text(),
            callback=done_cb)

    def on_activated(self, tree, it, column):
        entry = self.results[it]

        if entry[3] == NEXT_ID:
            done_cb = show_notify(self.widget, _("Searching..."))
            self.results.next_page(callback=done_cb)
            return
        elif entry[3] == PREV_ID:
            done_cb = show_notify(self.widget, _("Searching..."))
            self.results.prev_page(callback=done_cb)
            return

    # ---

    def _construct(self):
        box = gtk.VBox()
        box.set_spacing(5)
        self.widget = box

        self.search_title = gtk.Entry()
        self.search_author = gtk.Entry()
        self.search_button = gtk.Button(_("Search"))

        tbl = gtk.Table(rows=3, columns=2)
        tbl.attach(gtk.Label(_("Title:")), 0, 1, 0, 1,
                   xoptions=gtk.FILL)
        tbl.attach(self.search_title, 1, 2, 0, 1,
                   xoptions=gtk.EXPAND|gtk.FILL)
        tbl.attach(gtk.Label(_("Author:")), 0, 1, 1, 2,
                   xoptions=gtk.FILL)
        tbl.attach(self.search_author, 1, 2, 1, 2,
                   xoptions=gtk.EXPAND|gtk.FILL)
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

        self.widget_tree.append_column(author_col)
        self.widget_tree.append_column(title_col)
        self.widget_tree.append_column(lang_col)

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
        self.widget.set_border_width(10)

        # Notebook packing
        self.notebook = gtk.Notebook()
        self.notebook.set_show_border(False)
        self.widget.add(self.notebook)

        # Local ebooks tab
        page = gtk.VBox()
        page.pack_end(self.ebook_list.widget, expand=True, fill=True)
        self.notebook.append_page(page, gtk.Label(_("Books")))

        # Gutenberg tab
        page = gtk.VBox()
        page.pack_end(self.gutenberg_search.widget, expand=True, fill=True)
        self.notebook.append_page(page, gtk.Label(_("Gutenberg")))
        
        # Menu

        # Ebook context menu

    #-- Signals

    def on_destroy(self, ev):
        gtk.main_quit()

def main():
    p = optparse.OptionParser()
    options, args = p.parse_args()
    
    app = GutenbrowseApp(args[0])
    app.run()
