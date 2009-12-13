"""
Ebook text

"""
from ui import gtk

import os
import gzip
import bz2
import zipfile
import textwrap
import re

class EbookText(gtk.TextBuffer):
    def __init__(self, filename):
        self._text = None
        self._error = None
        self._load(filename)

        gtk.TextBuffer.__init__(self)
        if self._text:
            self.set_text(self._text)

    @property
    def loaded(self):
        return self._text is not None

    @property
    def error(self):
        return str(self._error)

    def _load(self, filename):
        try:
            if filename.endswith('.gz'):
                f = gzip.open(filename, 'r')
            elif filename.endswith('.bz2'):
                f = bz2.BZ2File(filename, 'r')
            else:
                f = open(filename, 'r')
            raw_text = f.read()
            f.close()

            for encoding in detect_encoding(raw_text):
                try:
                    self._text = unicode(raw_text, encoding)
                except UnicodeError:
                    pass

            self._text = rewrap(self._text)
        except IOError, e:
            self._text = None
            self._error = e

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
    text = text.replace(u'\r', u'')
    text = textwrap.dedent(text)
    text = re.sub(u'\n(?!\\s)', u' ', text)
    return text

if __name__ == "__main__":
    text = EbookText("test.txt.bz2")
    print text._text
