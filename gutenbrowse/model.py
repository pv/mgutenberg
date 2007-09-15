import re, os
import gtk
import gutenbergweb

from gettext import gettext as _
from guithread import *

def _is_caps_case(x):
    if len(x) < 1:
        return False
    elif len(x) == 1:
        return x[0] == x[0].upper()
    else:
        return x[0] == x[0].upper() and x[1] == x[1].lower()

def get_valid_basename(base):
    valid_ext = ['.txt', '.pdb', '.html']
    skip_ext = ['.gz', '.bz2', '.tar']

    while True:
        base, ext = os.path.splitext(base)
        if ext in valid_ext:
            return base
        elif ext in skip_ext:
            pass
        else:
            return None

FILE_RES = [
    re.compile(r"^(?P<auth>[^-\[\]]+) - (?P<titl>[^\[\]]+) \[(?P<lang>.*)\]$"),
    re.compile(r"^(?P<auth>[^-]+) - (?P<titl>.+)$"),
    re.compile(r"^(?P<titl>[^\[\]]+) \[(?P<lang>.+)\]$"),
    re.compile(r"^(?P<titl>.+)$")
]

class EbookList(gtk.ListStore):
    """
    List of ebooks:

        [(author, title, language, file_name), ...]
    """
    
    def __init__(self, base_directory):
        gtk.ListStore.__init__(self, str, str, str, str)
        self.base_directory = base_directory
    
    def add(self, author=u"", title=u"", language=u"", file_name=""):
        self.append((author, title, language, file_name))

    def refresh(self, sort=False):
        self.clear()

        def walk_tree(d, author_name=""):
            files = []
            for path in os.listdir(d):
                full_path = os.path.join(d, path)
                if os.path.isdir(full_path):
                    # recurse into a directory
                    was_author = (',' in author_name or
                                  _is_caps_case(author_name))
                    if not author_name or not was_author:
                        files.extend(walk_tree(full_path, path))
                    else:
                        files.extend(walk_tree(full_path, author_name))
                else:
                    base = get_valid_basename(path)
                    if base is None:
                        continue # not a valid file
                    
                    # a file or something like that
                    entry = None
                    for reg in FILE_RES:
                        m = reg.match(base)
                        if m:
                            g = m.groupdict()
                            entry = (g.get('auth', author_name),
                                     g.get('titl', base),
                                     g.get('lang', ''),
                                     full_path)
                            break
                    if entry is None:
                        entry = (author_name, base, "", full_path)
                    files.append(entry)
            return files

        def really_add(r):
            # Inserting stuff to GtkTreeView goes slowly on Maemo,
            # so we slow down the rate a bit. This makes the app usable
            # during insertion...
            for x in r[:100]:
                self.append(x)
            del r[:100]
            if r:
                run_later_in_gui_thread(200, really_add, r)

        def do_walk_tree(d):
            files = walk_tree(self.base_directory)
            if sort:
                files.sort()
            run_in_gui_thread(really_add, files)

        start_thread(do_walk_tree, self.base_directory)


NEXT_ID = -1
PREV_ID = -2

class GutenbergSearchList(gtk.ListStore):
    """
    List of search results:

        [(author, title, language, etext_id), ...]
    """
    
    def __init__(self):
        gtk.ListStore.__init__(self, str, str, str, int)
        self.pageno = 0
        self.max_pageno = None
        self.last_search = None
        
    def add(self, author=u"", title=u"", language=u"", etext_id=-1):
        self.append((author, title, language, etext_id))
        
    def new_search(self, author="", title=""):
        self.last_search = (author, title)
        self.pageno = 0
        self.max_pageno = None

        def on_finish(r):
            if not r:
                self.max_pageno = 0
            self._repopulate(r)

        run_in_background(gutenbergweb.search, author, title, pageno=0,
                          callback=on_finish)

    def next_page(self):
        if self.max_pageno is not None and self.pageno >= self.max_pageno:
            return # nothing to do
        
        def on_finish(r):
            if not r:
                self.max_pageno = self.pageno
            else:
                self.pageno += 1
                self._repopulate(r)

        run_in_background(gutenbergweb.search, self.last_search[0],
                          self.last_search[1], pageno=self.pageno + 1,
                          callback=on_finish)
        
    def prev_page(self):
        if self.pageno > 0:
            self.pageno -= 1
        else:
            return
        
        def on_finish(r):
            self.pageno -= 1
            self._repopulate(r)
        
        run_in_background(gutenbergweb.search, self.last_search[0],
                          self.last_search[1], pageno=self.pageno - 1,
                          callback=on_finish)
    
    def _repopulate(self, r):
        self.clear()

        if self.pageno > 0:
            self.add(_('(Previous...)'), '', '', PREV_ID)

        for x in r:
            self.add(x[1], x[2], x[3], x[0])
            
        if self.max_pageno is None or self.pageno < self.max_pageno:
            self.add(_('(Next...)'), '', '', NEXT_ID)
        
    def get_downloads(self, it):
        author, title, language, etext_id = self[it]
        info = DownloadInfo(author, title, language, etext_id)

        def on_finish(r):
            for url, format, encoding, compression in r:
                info.add(url, ', '.join(format, encoding, compression))

        run_in_background(gutenbergweb.etext_info, etext_id,
                          callback=on_finish)
        
        return info

class DownloadInfo(gtk.ListStore):
    """
    Download choices

        [(url, format info)]
    """
    def __init__(self, author, title, language, etext_id):
        self.author = author
        self.title = title
        self.language = language
        self.etext_id = etext_id

        gtk.ListStore.__init__(self, str, str)

    def add(self, url, format_info):
        self.append((url, format_info))
