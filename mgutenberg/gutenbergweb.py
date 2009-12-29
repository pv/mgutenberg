"""
Python interface to Project Gutenberg web catalog.

This may break at any time if they change page layout.

Routines
--------

- search(author, title, etextnr)

  Returns [(etext_id, authors, title, language, category), ...]

          authors = [(name, real_name, date, role), ...]

- etext_info(etext_id)

  Returns [(url, format, encoding, compression), ...]
"""
import urllib as _urllib, re as _re
from gettext import gettext as _

from util import *

#------------------------------------------------------------------------------
# Interface routines
#------------------------------------------------------------------------------

class SearchFailure(RuntimeError): pass

def search(author=None, title=None, etextnr=None, subject=None, pageno=0):
    """
    Search for an etext in the Project Gutenberg catalog

    :Returns:
        [(etext_id, authors, title, language, category), ...]

        authors = [(name, real_name, date, role), ...]
    """
    if not author:
        author = ''
    if not title:
        # NB. space switches to better Gutenberg search output
        title = ' '
    if not etextnr:
        etextnr = ''
    if not subject:
        subject = ''

    data = _urllib.urlencode([('author', unicode(author)),
                              ('title', unicode(title)),
                              ('subject', unicode(subject)),
                              ('etextnr', unicode(etextnr)),
                              ('pageno', unicode(pageno))])
    url = _SEARCH_URL + '?' + data
    
    output = _fetch_page(url)
    entries = _parse_gutenberg_search_html(output)
    
    # NB. Gutenberg search sometimes return duplicate entries
    return unique(entries, key=lambda x: x[0])

def etext_info(etext_id):
    """
    Get info concerning an Etext in the Project Gutenberg catalog

    :Returns:
        [(url, format, encoding, compression), ...], infodict

        infodict contains information about the whole entry.
        Keys: 'category'
    """
    output = _fetch_page(_ETEXT_URL % dict(etext=etext_id))
    return _parse_gutenberg_ebook_html(etext_id, output)

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

_TAG_RE = _re.compile("<[^>]+>")

def _fetch_page(url):
    h = myurlopen(url)
    try:
        return h.read()
    finally:
        h.close()

def _strip_tags(snippet):
    snippet = snippet.replace("&nbsp;", " ")
    snippet = snippet.replace("&quot;", "\"")
    snippet = snippet.replace("\r", " ")
    snippet = snippet.replace("\n", " ")
    snippet = snippet.replace("<br>", "\n")
    snippet = snippet.replace("<li>", "\n")
    return _TAG_RE.subn('', snippet)[0]

#------------------------------------------------------------------------------
# Urls
#------------------------------------------------------------------------------

_SEARCH_URL = "http://www.gutenberg.org/catalog/world/results"
_ETEXT_URL = "http://www.gutenberg.org/etext/%(etext)d"
_PLUCKER_URL = "http://www.gutenberg.org/cache/plucker/%(etext)d/%(etext)d"
_DOWNLOAD_URL_BASE = "http://www.gutenberg.org"

#------------------------------------------------------------------------------
# Page parsing
#------------------------------------------------------------------------------

#-- Search result page

_GUTEN_SEARCH_RE_1 = _re.compile("""
.*?
<tr\s+class=".*?">
  \s*
  <td>(?P<etext>.*?)</td>
  \s*
  <td>(?P<infocol>.*?)</td>
  \s*
  <td>
    (?P<authors>.*?)
  </td>
  \s*
  <td>
    \s*
    <a\s+href="/etext/(?P<etext2>.*?)">
      (?P<title>.*?)
    </a>
    \s*
  </td>
  \s*
  <td>(?P<language>.*?)</td>
  \s*
</tr>
""", _re.X | _re.I)

def _parse_gutenberg_search_html(html):
    """
    Parse search result page HTML
    """
    entries = []

    # "Parse" entries
    h = html
    while h:
        m = _GUTEN_SEARCH_RE_1.search(h)
        if m:
            h = h[m.end():]
            g = m.groupdict()

            try:
                etext = int(g['etext'])
            except (KeyError, ValueError):
                continue

            if 'stock_volume' in g.get('infocol', ''):
                category = _(u'Audio book')
            else:
                category = u''

            entries.append((
                etext,
                _parse_gutenberg_authors(unicode(_strip_tags(g.get('authors', '')), 'utf-8')),
                unicode(_strip_tags(g.get('title', '')), 'utf-8'),
                unicode(_strip_tags(g.get('language', '')), 'utf-8'),
                category,
                ))
        else:
            break

    return entries

#-- Ebook info page

_GUTEN_ETEXT_RE_0 = _re.compile("""
.*?
<th>Category</th>\s*<td><a[^>]*>(?P<category>[^>]*)</a>
""", _re.X | _re.I)

_GUTEN_ETEXT_RE_1 = _re.compile("""
.*?
<tr\s+class=".*?">
  .*?
  <td[^>]*format[^>]*>(?P<format>.*?)</td>\s*
  <td[^>]*encoding[^>]*>(?P<encoding>.*?)</td>\s*
  <td[^>]*compression[^>]*>(?P<compression>.*?)</td>\s*
  <td[^>]*size[^>]*>(?P<size>.*?)</td>\s*
  <td[^>]*download[^>]*>
    \s*
    <a\s+href="(?P<url>.*?)".*?
  </td>\s*
</tr>
""", _re.X | _re.I)

def _parse_gutenberg_ebook_html(etext, html):
    """
    Parse etext page HTML
    """
    entries = []
    
    if '/cache/plucker' in html:
        entries.append((
            _PLUCKER_URL % dict(etext=etext),
            'plucker',
            'plucker',
            'plucker'
            ))

    category = u''
    
    h = html

    m = _GUTEN_ETEXT_RE_0.search(h)
    if m:
        h = h[m.end():]
        g = m.groupdict()
        category = unicode(_strip_tags(g.get('category', '').strip()),
                           'utf-8')
    
    while h:
        m = _GUTEN_ETEXT_RE_1.search(h)
        if m:
            h = h[m.end():]
            g = m.groupdict()

            url = g.get('url', '').strip()
            format = unicode(_strip_tags(g.get('format', '')).lower().strip(),
                             'utf-8')
            encoding = unicode(_strip_tags(g.get('encoding', '')).lower().strip(),
                               'utf-8')
            compression = unicode(_strip_tags(g.get('compression', '')).lower().strip(),
                                  'utf-8')
            if encoding == 'none':
                encoding = ''
            if compression == 'none':
                compression = ''
            if format == 'none':
                format = ''

            if url:
                if url.startswith('/'):
                    url = _DOWNLOAD_URL_BASE + url
                entries.append((url, format, encoding, compression))

        else:
            break

    return entries, dict(category=category)

#-- Author name lists

def _parse_gutenberg_authors(aut):
    authors = []

    ss = aut.strip().split("\n")
    for row in ss:
        s = row.strip()
        name = u''
        real_name = u''
        role = u''
        date = u''
        title = u''

        # Role
        m = _re.search(ur'\[(\w+)\]\s*$', s)
        if m:
            role = m.group(1).lower()
            s = s[:m.start()]

        # Date
        for dt in (ur'(\d+\??-\d+\??)\s*$', ur'(\d+\??-)\s*$',
                   ur'(-\d+\??)\s*$', ur'(\d+\??\s+BC-\d+\??\s+BC)',
                   ur'(\d+\??\s+BC-)', ur'(-\d+\??\s+BC)',
                   ):
            m = _re.search(dt, s)
            if m:
                date = m.group(1)
                s = s[:m.start()]
                break

        s = _re.sub(ur',\s*$', '', s)

        # Title fragments
        m = _re.search(ur'\)(,\s+[^\)]+)\s*$', s)
        if m:
            title = m.group(1)
            s = s[:m.start()+1]

        # Real name
        m = _re.search(ur'\(([^\)]+)\)\s*$', s)
        if m:
            real_name = m.group(1).strip()
            s = s[:m.start()]

        # Name
        name = s.strip()
        if not name:
            if row.strip():
                authors.append((row.strip(), u'', u'', u''))
        else:
            authors.append((name, real_name+title, date, role))

    return authors
