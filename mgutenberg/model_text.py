"""
Ebook text

"""
from ui import gtk
import pango

import os
import gzip
import bz2
import zipfile
import textwrap
import re
from StringIO import StringIO

from HTMLParser import HTMLParser
import htmlentitydefs

import plucker

class EbookText(gtk.TextBuffer):
    def __init__(self, filename):
        gtk.TextBuffer.__init__(self)

        self._text = None
        self._error = None
        self._load(filename)

        if self._text:
            self.set_text(self._text)

    @property
    def loaded(self):
        return self._text is not None

    @property
    def error(self):
        if not self._error:
            return None
        return str(self._error)

    def _load(self, filename):
        try:
            basefn, ext = os.path.splitext(filename)
            if ext == '.gz':
                f = gzip.open(filename, 'rb')
                filename = basefn
            elif ext == '.bz2':
                f = bz2.BZ2File(filename, 'rb')
                filename = basefn
            elif ext == '.zip':
                zf = zipfile.ZipFile(filename, 'r')
                names = zf.namelist()
                if len(names) != 1:
                    raise IOError("Zip file does not contain a single file")
                f = StringIO(zf.read(names[0]))
                zf.close()
                filename = names[0]
            elif ext == '.pdb':
                f = plucker.PluckerFile(filename)
            else:
                f = open(filename, 'rb')

            self._load_stream(filename, f)
            f.close()
        except IOError, e:
            self._text = None
            self._error = e

    def _load_stream(self, filename, f):
        basefn, ext = os.path.splitext(filename)
        if ext in ('.html', '.htm'):
            self._load_html(f)
        elif ext in ('.txt', '.rst'):
            self._load_plain_text(f)
        elif ext in ('.pdb'):
            self._load_plucker(f)
        else:
            raise IOError("Don't know how to open this type of files")

    def _load_html(self, f):
        if isinstance(f, str):
            raw_text = str
        else:
            raw_text = f.read()

        for encoding in detect_encoding(raw_text):
            try:
                raw_text = unicode(raw_text, encoding)
                break
            except UnicodeError:
                pass

        tag_bold = self.create_tag("bold", weight=pango.WEIGHT_BOLD)
        tag_emph = self.create_tag("emph", style=pango.STYLE_ITALIC)
        tag_big = self.create_tag("big", scale=1.5)

        parent = self

        class HandleHTML(HTMLParser):
            tags = []
            in_body = False
            encoding = 'latin1'
            para = u""
            omit = 0
            slurp_space = True

            def handle_starttag(self, tag, attrs):
                self.flush()
                if tag in ('h1', 'h2', 'h3', 'h4'):
                    self._append(u'\n\n')
                    self.tags.append(tag_big)
                elif tag == 'p' or tag == 'br' or tag == 'div':
                    self.tags = []
                    self._append(u'\n')
                    self.slurp_space = True
                elif tag == 'tr':
                    self.tags = []
                    self._append(u'\n')
                    self.slurp_space = True
                elif tag == 'td':
                    self._append(u'\t')
                elif tag == 'i' or tag == 'em':
                    self.tags.append(tag_emph)
                elif tag == 'b' or tag == 'strong' or tag == 'bold':
                    self.tags.append(tag_bold)
                elif tag == 'hr':
                    self._append(u'\n')
                elif tag == 'body':
                    self.in_body = True
                elif tag == 'style':
                    self.omit += 1
                elif tag == 'meta' and not self.in_body:
                    self.handle_meta(attrs)
                elif tag == 'img':
                    attrs = dict(attrs)
                    if 'alt' in attrs and attrs['alt'].strip():
                        self.handle_data('[IMAGE: %s]' % attrs['alt'].strip())
                    else:
                        self.handle_data('[IMAGE]')

            def handle_meta(self, attrs):
                attrs = dict(attrs)
                if not attrs.get('http-equiv', "").lower() == 'content-type':
                    return
                content = attrs.get('content', "")

                m = re.search(r'charset\s*=\s*([a-zA-Z0-9-]+)', content)
                if m:
                    encoding = m.group(1).lower()
                    try:
                        unicode('', encoding)
                        self.encoding = encoding
                    except UnicodeError:
                        pass

            def handle_endtag(self, tag):
                self.flush()
                if tag == 'style':
                    self.omit -= 1
                elif tag in ('h1', 'h2', 'h3', 'h4'):
                    if self.tags:
                        self.tags.pop()
                    self._append('\n')
                elif tag in ('i', 'em', 'b', 'strong', 'bold'):
                    if self.tags:
                        self.tags.pop()

            def handle_data(self, data):
                if self.omit:
                    return
                data = data.replace('\r', '')
                data = data.replace('\n', ' ')
                if self.slurp_space:
                    data = data.lstrip()
                self.para += data
                self.slurp_space = False

            def handle_charref(self, name):
                try:
                    self.para += unicode(chr(int(name)), 'latin1')
                except (UnicodeError, ValueError):
                    self.para += '?'

            def handle_entityref(self, name):
                self.para += u'%c' % htmlentitydefs.name2codepoint.get(name, 63)

            def _append(self, text):
                parent.insert_with_tags(parent.get_end_iter(),
                                        text.encode('utf-8'), *self.tags)

            def flush(self):
                if self.para:
                    self._append(self.para)
                    self.para = u""

        html = HandleHTML()
        html.feed(raw_text)
        html.flush()

    def _load_plucker(self, f):
        tag_bold = self.create_tag("bold", weight=pango.WEIGHT_BOLD)
        tag_emph = self.create_tag("emph", style=pango.STYLE_ITALIC)
        tag_big = self.create_tag("big", scale=1.5)

        def set_tag(tag, flag):
            if tag in tags:
                if not flag:
                    tags.remove(tag)
            else:
                if flag:
                    tags.append(tag)

        def flush_text():
            if not text:
                return
            self.insert_with_tags(self.get_end_iter(),
                                  u"".join(text).encode('utf-8'),
                                  *tags)
            del text[:]

        tags = []
        text = []
        new_line = True
        for cmd, data in f:
            if cmd == 'text':
                if new_line:
                    data = data.lstrip()
                    new_line = False
                text.append(data)
            elif cmd == 'br':
                if not new_line:
                    text.append(u"\n")
                new_line = True
            elif cmd == 'para':
                flush_text()
                del tags[:]
                if not new_line:
                    text.append(u"\n")
                new_line = True
            elif cmd == 'em':
                flush_text()
                set_tag(tag_emph, data)
            elif cmd == 'font':
                flush_text()
                if data == 'b':
                    set_tag(tag_bold, True)
                elif data in ('h1','h2','h3','h4'):
                    set_tag(tag_big, True)
                else:
                    del tags[:]

    def _load_plain_text(self, f):
        if isinstance(f, str):
            raw_text = str
        else:
            raw_text = f.read()

        for encoding in detect_encoding(raw_text):
            try:
                self._text = unicode(raw_text, encoding)
                break
            except UnicodeError:
                pass

        self._text = rewrap(self._text)

def detect_encoding(text):
    encodings = ['utf-8']
    if '\x92' in text:
        encodings.append('windows-1250')
    else:
        encodings.append('latin1')
    return encodings

def rewrap(text):
    if not text:
        return

    # remove lines
    text = re.sub(r'-{10,}', '', text)
    text = re.sub(r'={10,}', '', text)

    text = text.replace(u'\r', u'')
    text = textwrap.dedent(text)

    sample = text[:80*1000]
    if len([x for x in sample.split('\n') if x.startswith(' ')]) > 20:
        # Paragraphs separated by indent
        text = re.sub(u'\n(?!\\s)', u' ', text)
    elif max(map(len, sample.split("\n"))) < 100 and sample.count('\n\n') > 5:
        # Paragraphs separated by empty lines
        text = re.sub(u'\n(?!\n)', u' ', text)
    else:
        # Paragraphs on a single line -- or couldn't determine formatting
        pass

    text = re.sub(u'\s{10,}', u'\n', text)
    text = re.sub(u'\n[ \t]+', u'\n', text)
    return text

if __name__ == "__main__":
    import cProfile as profile
    import time
    start = time.time()
    txt = EbookText('test.pdb')
    print time.time() - start

