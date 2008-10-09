import re, os, sys, shutil, tempfile
import xml.etree.ElementTree as ET
from xml.parsers.expat import ExpatError

import gtk
import gutenbergweb

from gettext import gettext as _
from guithread import *
from util import *

class OverwriteFileException(Exception): pass


def _is_caps_case(x):
    if len(x) < 1:
        return False
    elif len(x) == 1:
        return x[0] == x[0].upper()
    else:
        return x[0] == x[0].upper() and x[1] == x[1].lower()

def get_valid_basename(base):
    valid_ext = ['.txt',
                 '.html', '.htm',
                 '.fb2',
                 '.chm',
                 '.rtf',
                 '.oeb',
                 '.zip',
                 '.prc', '.pdb', '.mobi',
                 '.orb',
                 '.opf', '.oebzip',
                 '.tcr',
                 '.tgz', '.ipk',
                 ]
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
    
    def __init__(self, search_dirs):
        gtk.ListStore.__init__(self, str, str, str, str)
        self.search_dirs = search_dirs
    
    def add(self, author=u"", title=u"", language=u"", file_name=""):
        return self.append((author, title, language, file_name))

    def refresh(self, callback=None):
        self.clear()

        def walk_tree(files, d, author_name=""):
            if not os.path.isdir(d):
                return

            try:
                paths = os.listdir(d)
            except OSError:
                # permission error, etc.
                return
            
            for path in paths:
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
                callback(True)
        
        def do_walk_tree(dirs):
            files = []
            for d in dirs:
                walk_tree(files, d)
            files.sort()
            run_in_gui_thread(really_add, files)

        start_thread(do_walk_tree, self.search_dirs)

    def sync_fbreader(self, callback=None):

        def on_finish(r):
            if callback:
                callback(r)

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
        return self.append((author, title, language, category, etext_id))
        
    def new_search(self, author="", title="", callback=None):
        self.last_search = (author, title)
        self.pageno = 0
        self.max_pageno = None

        def on_finish(r):
            if isinstance(r, Exception):
                callback(r)
                return
            if not r:
                self.max_pageno = 0
            self._repopulate(r)
            if callback:
                callback(True)

        run_in_background(gutenbergweb.search, author, title, pageno=0,
                          callback=on_finish)

    def next_page(self, callback=None):
        if self.max_pageno is not None and self.pageno >= self.max_pageno:
            return # nothing to do
        
        def on_finish(r):
            if isinstance(r, Exception):
                callback(r)
                return
            if not r:
                self.max_pageno = self.pageno
                r = self.last_result # remove the dummy navigation entry
            else:
                self.pageno += 1
            self._repopulate(r)
            if callback:
                callback(True)

        run_in_background(gutenbergweb.search, self.last_search[0],
                          self.last_search[1], pageno=self.pageno + 1,
                          callback=on_finish)
        
    def prev_page(self, callback=None):
        if self.pageno > 0:
            self.pageno -= 1
        else:
            return
        
        def on_finish(r):
            if isinstance(r, Exception):
                callback(r)
                return
            self.pageno -= 1
            self._repopulate(r)
            if callback:
                callback(True)
        
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
            if isinstance(result, Exception):
                callback(result)
                return
                
            r, infodict = result
            info.category = infodict['category']
            for url, format, encoding, compression in r:
                msg = [x for x in format, encoding, compression if x]
                info.add(url, ', '.join(msg))
            if callback:
                callback(info)

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
        return self.append((url, format_info))

    def download(self, it, base_directory, overwrite=False, callback=None):
        """
        :Parameters:
            it : gtk tree iterator
                Which item to download
            base_directory : str
                Directory under which to download
            overwrite : bool
                Allow overwriting existing files
            callback: callable(path)
                Function to call when download finished.
                ``path`` is the name of the new file, if the download was
                successful, and None if it download failed.
        """
        url, format = self[it]

        author = clean_filename(clean_author(self.author))

        url_base = url.split('/')[-1]
        try:
            ext = url_base.split('.', 1)[1]
        except IndexError:
            ext = ''

        if not ext and 'plucker' in format:
            ext = 'pdb'
            url_base += '.pdb'

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

        if os.path.isfile(path) and not overwrite:
            raise OverwriteFileException()
        
        dir_path = os.path.dirname(path)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        def do_download(url):
            h, f = None, None
            try:
                h = myurlopen(url)
                f = open(path, 'w')
                shutil.copyfileobj(h, f)
            except IOError, e:
                # fetch failed; remove if exists and signal error
                if os.path.isfile(path):
                    os.remove(path)
                
                return e
            finally:
                if h is not None: h.close()
                if f is not None: f.close()
                
            return path
        
        def on_finish(path):
            if callback:
                callback(path)
        
        run_in_background(do_download, url, callback=on_finish)

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
    home = os.path.expanduser("~")

    if booklist_fn is None:
        booklist_fn = os.path.join(home, '.FBReader', 'books.xml')

    if state_fn is None:
        state_fn = os.path.join(home, '.FBReader', 'state.xml')

    seen = {}

    out_books = tempfile.TemporaryFile()
    out_state = tempfile.TemporaryFile()

    #
    # -- Manipulate book list
    #

    if os.path.isfile(booklist_fn):
        f = open(booklist_fn, 'r')
        try:
            tree = ET.parse(f)
        except ExpatError:
            tree = ET.ElementTree(ET.Element('config'))
        finally:
            f.close()
    else:
        d = os.path.dirname(booklist_fn)
        if not os.path.isdir(d):
            os.makedirs(d)
        tree = ET.ElementTree(ET.Element('config'))

    root = tree.getroot()

    # Update entries
    for group in root.getiterator('group'):
        fn = group.get('name')
        
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

    if os.path.isfile(state_fn):
        f = open(state_fn, 'r')
        try:
            tree = ET.parse(f)
        except ExpatError:
            tree = ET.ElementTree(ET.Element('config'))
        finally:
            f.close()
    else:
        d = os.path.dirname(state_fn)
        if not os.path.isdir(d):
            os.makedirs(d)
        tree = ET.ElementTree(ET.Element('config'))
    
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

def run_fbreader(path):
    # XXX: Better support for audio books
    cmd = ['FBReader', path]
    os.spawnvp(os.P_NOWAIT, cmd[0], cmd)

class Config(dict):
    """
    Very simple configuration file with basic-type XML object serialization
    """
    def __init__(self, schema):
        home = os.path.expanduser("~")
        self.file_name = os.path.join(home, '.gutenbrowserc')
        self.schema = schema

    def _toxml(self, o):
        if isinstance(o, list):
            el = ET.Element('list')
            for x in o:
                el.append(self._toxml(x))
            return el
        elif isinstance(o, dict):
            el = ET.Element('dict')
            for k, v in o.iteritems():
                e = self._toxml(v)
                e.attrib['key'] = str(k)
                el.append(e)
            return el
        elif isinstance(o, int):
            return ET.Element('int', dict(value=str(o)))
        elif isinstance(o, float):
            return ET.Element('float', dict(value=str(o)))
        elif isinstance(o, str) or isinstance(o, unicode):
            return ET.Element('str', dict(value=o))
        else:
            raise NotImplementedError

    def _fromxml(self, el):
        valf = {'int': int, 'str': str, 'float': float}

        if el.tag == 'list':
            o = []
            for sel in el:
                o.append(self._fromxml(sel))
            return o
        elif el.tag == 'dict':
            o = {}
            for sel in el:
                k = sel.get('key')
                if k is None: continue
                o[k] = self._fromxml(sel)
            return o
        elif el.tag in valf:
            try:
                return valf[el.tag](el.get('value'))
            except ValueError:
                return None
        else:
            return None

    def load(self):
        f = open(self.file_name, 'r')
        try:
            tree = ET.parse(f)
            d = self._fromxml(tree.getroot())
            self._coerce_schema(d)
            self.clear()
            self.update(d)
        except ExpatError:
            pass
        finally:
            f.close()

    def save(self):
        f = open(self.file_name, 'w')
        try:
            root = self._toxml(self)
            tree = ET.ElementTree(root)
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding='utf-8')
        finally:
            f.close()

    def _coerce_schema(self, d):
        """
        Coerce config to a schema:

            schema = {'key1': (list, str),
                      'key2': (dict, str), ...}

        drop non-valid keys.
        """

        class WalkError(RuntimeError): pass
        
        def walk(x, types):
            if not types:
                raise WalkError()
            
            t = types[0]
            
            if not isinstance(x, t):
                raise WalkError()
            
            if t == dict:
                for k, v in x.iteritems():
                    if not isinstance(k, str):
                        raise WalkError()
                    walk(v, types[1:])
            elif t == list:
                for y in x:
                    walk(y, types[1:])
            elif len(types) > 1:
                raise WalkError()
            else:
                pass # OK

        for k, v in self.iteritems():
            try:
                if k not in self.schema:
                    raise WalkError()

                types = self.schema[k]
                if not hasattr(types, '__iter__'):
                    types = (types,)

                walk(v, types)
            except WalkError:
                del d[k]
