import re, os, sys, shutil, urllib, tempfile
import elementtree.ElementTree as ET

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

LANGUAGE_CODE_MAP = {
    'english': 'en',
    'german': 'de',
    'finnish': 'fi',
}

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

    def refresh(self, callback=None):
        self.clear()

        def walk_tree(files, d, author_name=""):
            for path in os.listdir(d):
                full_path = os.path.join(d, path)
                if os.path.isdir(full_path):
                    # recurse into a directory
                    was_author = (',' in author_name)
                    if not author_name or not was_author:
                        walk_tree(files, full_path, path)
                    else:
                        walk_tree(files, full_path, author_name)
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

        def really_add(r):
            for x in r:
                self.append(x)
            if callback:
                callback()
        
        def do_walk_tree(d):
            files = []
            walk_tree(files, self.base_directory)
            files.sort()
            run_in_gui_thread(really_add, files)

        start_thread(do_walk_tree, self.base_directory)

    def sync_fbreader(self, callback=None):

        def on_finish(r):
            if callback: callback()

        file_map = dict((os.path.realpath(r[3]),
                         (r[0], r[1], r[2])) for r in self)
        
        run_in_background(sync_fbreader, file_map,
                          callback=on_finish)
        
NEXT_ID = -10
PREV_ID = -20

class GutenbergSearchList(gtk.ListStore):
    """
    List of search results:

        [(author, title, language, category, etext_id), ...]
    """
    
    def __init__(self):
        gtk.ListStore.__init__(self, str, str, str, str, int)
        self.pageno = 0
        self.max_pageno = None
        self.last_search = None
        self.last_result = None
        
    def add(self, author=u"", title=u"", language=u"",
            category=u"", etext_id=-1):
        self.append((author, title, language, category, etext_id))
        
    def new_search(self, author="", title="", callback=None):
        self.last_search = (author, title)
        self.pageno = 0
        self.max_pageno = None

        def on_finish(r):
            if not r:
                self.max_pageno = 0
            self._repopulate(r)
            if callback:
                callback()

        run_in_background(gutenbergweb.search, author, title, pageno=0,
                          callback=on_finish)

    def next_page(self, callback=None):
        if self.max_pageno is not None and self.pageno >= self.max_pageno:
            return # nothing to do
        
        def on_finish(r):
            if not r:
                self.max_pageno = self.pageno
                r = self.last_result # remove the dummy navigation entry
            else:
                self.pageno += 1
            self._repopulate(r)
            if callback:
                callback()

        run_in_background(gutenbergweb.search, self.last_search[0],
                          self.last_search[1], pageno=self.pageno + 1,
                          callback=on_finish)
        
    def prev_page(self, callback=None):
        if self.pageno > 0:
            self.pageno -= 1
        else:
            return
        
        def on_finish(r):
            self.pageno -= 1
            self._repopulate(r)
            if callback:
                callback()
        
        run_in_background(gutenbergweb.search, self.last_search[0],
                          self.last_search[1], pageno=self.pageno - 1,
                          callback=on_finish)
    
    def _repopulate(self, r):
        self.last_result = r
        self.clear()
        
        if self.pageno > 0:
            self.add(_('(Previous...)'), '', '', '', PREV_ID)

        for x in r:
            self.add(x[1], x[2], x[3], x[4], x[0])
            
        if self.max_pageno is None or self.pageno < self.max_pageno:
            self.add(_('(Next...)'), '', '', '', NEXT_ID)
        
    def get_downloads(self, it, callback=None):
        author, title, language, category, etext_id = self[it]
        info = DownloadInfo(author, title, language, category, etext_id)

        def on_finish(result):
            r, infodict = result
            info.category = infodict['category']
            for url, format, encoding, compression in r:
                msg = [x for x in format, encoding, compression if x]
                info.add(url, ', '.join(msg))
            if callback:
                callback()

        run_in_background(gutenbergweb.etext_info, etext_id,
                          callback=on_finish)
        
        return info

class DownloadInfo(gtk.ListStore):
    """
    Download choices

        [(url, format info)]
    """
    def __init__(self, author, title, language, category, etext_id):
        self.author = author
        self.title = title
        self.language = language
        self.category = category
        self.etext_id = etext_id

        gtk.ListStore.__init__(self, str, str)

    def add(self, url, format_info):
        self.append((url, format_info))

    def download(self, it, base_directory, overwrite=False, callback=None):
        url, format = self[it]

        author = clean_filename(clean_author(self.author))

        url_base = url.split('/')[-1]
        try:
            ext = url_base.split('.', 1)[1]
        except IndexError:
            ext = ''

        if self.author and self.title and self.language:
            base_name = u"%s - %s [%s]" % (author,
                                           self.title,
                                           self.language.lower())
        elif self.author and self.title:
            base_name = u"%s - %s" % (author, self.title)
        elif self.title:
            base_name = u"%s" % self.title
        else:
            base_name = u"Etext %d" % self.etext_id
        
        if ext:
            if get_valid_basename(url_base) is None:
                # Download audio files w/o renaming
                file_name = clean_filename(url_base)
            else:
                file_name = clean_filename("%s.%s" % (base_name, ext))
        else:
            file_name = clean_filename(base_name)

        if author:
            path = os.path.join(base_directory, author, file_name)
        else:
            path = os.path.join(base_directory, file_name)
        dir_path = os.path.dirname(path)

        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        if os.path.isfile(path) and not overwrite:
            return False
        
        def do_download():
            h = urllib.urlopen(url)
            f = open(path, 'w')
            try:
                shutil.copyfileobj(h, f)
            finally:
                h.close()
                f.close()
            return path

        def on_finish(path):
            if callback:
                callback(path)
        
        run_in_background(do_download, callback=on_finish)
        return True

_AUTHOR_RES = [
    re.compile(r"^(.*?),\s*\d.*$", re.S),
    re.compile(r"^(.*?);.*$", re.S),
    ]

def clean_author(au):
    """
    Remove cruft from Project Gutenberg author strings
    """
    au = au.strip()
    for r in _AUTHOR_RES:
        m = r.match(au)
        if m:
            return m.group(1)
    return au

def clean_filename(s):
    """
    Encode file name in filesystem charset and remove illegal characters
    """
    s = unicode(s).encode(sys.getfilesystemencoding(), 'replace')
    # cleanup for VFAT and others
    s = re.sub(r'[\x00-\x1f"\*\\/:<>?|]', '', s)
    return s

def sync_fbreader(file_map, booklist_fn=None, state_fn=None):
    """
    Synchronize FBReader book list.

    :Parameters:
        file_map : { file_name: (author, title, language), ... }
    """
    home = os.environ.get('HOME')

    if booklist_fn is None:
        if home is None:
            return False # can't
        booklist_fn = os.path.join(home, '.FBReader', 'books.xml')

    if state_fn is None:
        if home is None:
            return False # can't
        state_fn = os.path.join(home, '.FBReader', 'state.xml')

    seen = {}

    out_books = tempfile.TemporaryFile()
    out_state = tempfile.TemporaryFile()

    #
    # -- Manipulate book list
    #

    f = open(booklist_fn, 'r')
    try:
        tree = ET.parse(f)
    finally:
        f.close()

    root = tree.getroot()

    # Update entries
    for group in root.getiterator('group'):
        fn = group.get('name')
        if not os.path.isfile(fn):
            print fn
        if fn in file_map:
            seen[fn] = True
            base = get_valid_basename(os.path.basename(fn))
            author, title, language = file_map[fn]                
            for opt in group.getiterator('option'):
                name = opt.get('name', '')
                value = opt.get('value', '')
                if name == 'AuthorDisplayName':
                    if value == 'Unknown Author':
                        opt.set('value', author)
                elif name == 'AuthorSortKey':
                    if value == '___':
                        opt.set('value', author.lower())
                elif name == 'Title':
                    if value == base:
                        opt.set('value', title)
                elif name == 'Language':
                    if not value:
                        opt.set('value', LANGUAGE_CODE_MAP.get(language, ''))

    # Add missing entries
    for fn, (author, title, language) in file_map.iteritems():
        if fn in seen: continue

        try:
            r = os.stat(fn)
        except OSError:
            continue

        group = ET.SubElement(root, 'group', dict(name=fn))

        def add_options(*a):
            for name, value in zip(a[::2], a[1::2]):
                ET.SubElement(group, 'option', dict(name=name,value=value))

        add_options('AuthorDisplayName', author,
                    'AuthorSortKey', author.lower(),
                    'Initialized', 'true',
                    'BreakType', '6',
                    'Encoding', 'iso-8859-1',
                    'IgnoredIndent', '2',
                    'Size', str(r.st_size),
                    'Title', title,
                    'Language', LANGUAGE_CODE_MAP.get(language, 'none'),
                    )

    # Write
    out_books.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(out_books, encoding='utf-8')

    #
    # -- Manipulate state
    #

    f = open(state_fn, 'r')
    try:
        tree = ET.parse(f)
    finally:
        f.close()

    root = tree.getroot()
    try:
        booklist = [g for g in root.findall('group')
                    if g.get('name') == 'BookList'][0]
    except IndexError:
        booklist = ET.SubElement(root, 'group', dict(name='BookList'))
    
    seen = {}
    max_id = 0
    book_count = 0
    size_group = None

    for opt in booklist.getiterator('option'):
        name = opt.get('name')
        value = opt.get('value')
        if name.startswith('Book'):
            seen[value] = True
            book_count += 1
            try:
                max_id = max(int(name[4:]), max_id)
            except ValueError:
                pass
        elif name == 'Size':
            size_group = opt

    for fn, (author, title, language) in file_map.iteritems():
        if fn in seen: continue

        max_id += 1
        book_count += 1
        ET.SubElement(booklist, 'option',
                      dict(name='Book%d' % max_id,
                           value=fn))

    if size_group is None:
        size_group = ET.SubElement(booklist, 'option',
                                   dict(name='Size'))

    size_group.set('value', str(book_count))

    out_state.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    tree.write(out_state, encoding='utf-8')

    #
    # -- Replace FBReader files
    #
    out_books.seek(0)
    f = open(booklist_fn, 'w')
    try:
        shutil.copyfileobj(out_books, f)
    finally:
        f.close()
        out_books.close()

    out_state.seek(0)
    f = open(state_fn, 'w')
    try:
        shutil.copyfileobj(out_state, f)
    finally:
        f.close()
        out_state.close()

    return True
