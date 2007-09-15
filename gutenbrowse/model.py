import gtk
import gutenbergweb
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
        r = gutenbergweb.search(author, title, pageno=self.pageno)
        if not r:
            self.max_pageno = 0
        self._repopulate(r)

    def next_page(self):
        if self.max_pageno is None or self.pageno < self.max_pageno:
            self.pageno += 1
        else:
            return
        r = gutenbergweb.search(self.last_search[0], self.last_search[1],
                                pageno=self.pageno)
        if not r:
            self.pageno -= 1
            self.max_pageno = self.pageno
        else:
            self._repopulate(r)

    def prev_page(self):
        if self.pageno > 0:
            self.pageno -= 1
        else:
            return
        r = gutenbergweb.search(self.last_search[0], self.last_search[1],
                                pageno=self.pageno)
        self._repopulate(r)

    def _repopulate(self, r):
        self.clear()

        if self.pageno > 0:
            self.add(_('(Previous...)'), '', '', PREV_ID)

        for x in r:
            self.add(x[1], x[2], x[3], x[0])
            
        if self.max_pageno is None or self.pageno < self.max_pageno:
            self.add(_('(Next...)'), '', '', NEXT_ID)
