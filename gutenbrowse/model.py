import gtk
import gutenbergweb
from guithread import *
from gettext import gettext as _

class EbookList(gtk.ListStore):
    """
    List of ebooks:

        [(author, title, language, file_name), ...]
    """
    
    def __init__(self):
        gtk.ListStore.__init__(self, str, str, str, str)
    
    def add(self, author=u"", title=u"", language=u"", file_name=""):
        self.append((author, title, language, file_name))

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
