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


CONFIG_SCHEMA = {
    'search_dirs': (list, str),
    'save_dir': str,
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
        sdirs = ['/media/mmc1', '/media/mmc2', '/home/user/MyDocs/.documents']
        config.setdefault('search_dirs', sdirs)
        # XXX: Don't hardcode the save dir like this!
        config.setdefault('save_dir', '/media/mmc1/Books')
    else:
        sdirs = [os.path.join(os.path.expanduser("~"), "Desktop", "Books")]
        config.setdefault('search_dirs', sdirs)
        config.setdefault('save_dir', sdirs[0])

    # Run
    app = GutenbrowseApp(config)
    app.run()


# XXX: revise those deeply nested callbacks; try to reduce nesting of code

class GutenbrowseApp(AppBase):
    def __init__(self, config):
        AppBase.__init__(self)
        
        self.config = config
        self.ebook_list = EbookList(config['search_dirs'])
        self.window = MainWindow(self)
        
        if MAEMO:
            self.add_window(self.window.widget)
        
        # Refresh ebook list
        
        def done_cb(r):
            end_notify()
            self.window.ebook_list.thaw()
            if isinstance(r, Exception):
                self.app.error_message(_("Error refreshing book list"), r)
        
        end_notify = self.show_notify(self.window.widget,
                                      _("Finding books..."))
        self.window.ebook_list.freeze()
        self.ebook_list.refresh(callback=done_cb)

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

    def run(self):
        self.window.show_all()
        
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
              <menuitem action="fetch_url" />
              <menuitem action="fetch_file" />
              <separator/>
              <menuitem action="read" />
              <menuitem action="remove" />
              <separator name="quit_sep" />
              <menuitem name="quit" action="quit" />
            </menu>
            <menu action="tools">
              <menuitem action="update_fbreader" />
            </menu>
          </menubar>
          <popup name="ebook_popup">
            <menuitem action="read" />
            <menuitem action="remove" />
          </popup>
        </ui>
        """]
    else:
        UI_XMLS = ["""
        <ui>
          <popup name="menu_bar">
            <menuitem action="fetch_url" />
            <menuitem action="fetch_file" />
            <separator/>
            <menuitem action="read" />
            <menuitem action="remove" />
            <separator name="quit_sep" />
            <menuitem action="update_fbreader" />
            <separator name="quit_sep" />
            <menuitem name="quit" action="quit" />
          </popup>
          <popup name="ebook_popup">
            <menuitem action="read" />
            <menuitem action="remove" />
          </popup>
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

    # ---

    def on_action_fetch_url(self, action):
        pass # XXX: implement
    
    def on_action_fetch_file(self, action):
        pass # XXX: implement
    
    def on_action_read(self, action):
        pass # XXX: implement
    
    def on_action_remove(self, action):
        pass # XXX: implement
    
    def on_action_update(self, action):
        pass # XXX: implement

    def on_action_update_fbreader(self, action):
        def on_finish(r):
            notify_cb()
            if isinstance(r, Exception):
                self.app.error_message(_("Error updating FBReader"), r)

        notify_cb = self.app.show_notify(self.widget,
                                         _("Synchronizing FBReader..."))
        self.app.ebook_list.sync_fbreader(callback=on_finish)

    def on_action_quit(self, action):
        self.app.quit()

    def on_destroy(self, ev):
        self.app.quit()

    # ---

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

        # Menu &c
        actiongroup = gtk.ActionGroup('actiongroup')
        actiongroup.add_actions([
            ('file', None, _("_File")),
            ('fetch_url', None, _("_Fetch URL..."), None,
             None, self.on_action_fetch_url),
            ('fetch_file', None, _("_Fetch file..."), None,
             None, self.on_action_fetch_file),
            ('read', None, _("_Read"), None,
             None, self.on_action_read),
            ('remove', None, _("_Remove..."), None,
             None, self.on_action_remove),
            ('quit', gtk.STOCK_QUIT, _("_Quit"), None,
             None, self.on_action_quit),
            ('tools', None, _("_Tools")),
            ('update_fbreader', None, _("_Update FBReader book list"), None,
             None, self.on_action_update_fbreader),
        ])
        
        self.uim = gtk.UIManager()
        self.uim.insert_action_group(actiongroup, 0)
        for xml in self.UI_XMLS:
            self.uim.add_ui_from_string(xml)

        menu_bar = self.uim.get_widget('/menu_bar')

        if MAEMO:
            self.widget.set_menu(menu_bar)
        else:
            self.widget.add_accel_group(self.uim.get_accel_group())
            vbox.pack_start(menu_bar, fill=True, expand=False)
            vbox.reorder_child(menu_bar, 0)

        # Ebook context menu

        # XXX: implement

        # Status bar (non-Maemo)
        if not MAEMO:
            self.statusbar = gtk.Statusbar()
            vbox.pack_start(self.statusbar, expand=False, fill=True)

class EbookListWidget(object):
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
        
    def freeze(self):
        self.widget_tree.set_model(None)
        
    def thaw(self):
        self.widget_tree.set_model(self.store)

    # ---
    
    def on_activated(self, treeview, it, column):
        entry = treeview.get_model()[it]
        run_fbreader(entry[3])

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
        raw = ''.join([entry[0], entry[1], entry[2]]).lower()
        return all(x in raw for x in self.filter_text)
        
    # ---

    def _construct(self):
        box = gtk.VBox()
        self.widget = box

        # Filter entry
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Filter:")), fill=False, expand=False)
        self.filter_entry = gtk.Entry()
        hbox.pack_start(self.filter_entry, fill=True, expand=True)
        box.pack_start(hbox, fill=True, expand=False)

        # Tree
        scroll = gtk.ScrolledWindow()
        box.pack_start(scroll, fill=True, expand=True)

        self.widget_tree = gtk.TreeView(self.store)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        scroll.add(self.widget_tree)

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
        
        # optimizations for large lists
        self.widget_tree.set_fixed_height_mode(True)

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
                            run_fbreader(path)
                        dlg.destroy()
                    dlg.connect("response", response, path)
                    dlg.show()

            def proceed(selected, overwrite=False):
                self.info.download(selected,
                                   self.app.config['save_dir'],
                                   overwrite=overwrite,
                                   callback=lambda x: done_cb(x, notify_cb))
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
