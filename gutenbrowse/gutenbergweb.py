"""
Python interface to Project Gutenberg web catalog.

This may break at any time if they change page layout.

Routines
--------

- search(author, title, etextnr)

  Returns [(etext_id, authors, title, language), ...]
  
- etext_info(etext_id)

  Returns [(url, format, encoding, compression), ...]
"""
import urllib as _urllib, re as _re

#------------------------------------------------------------------------------
# Interface routines
#------------------------------------------------------------------------------

class SearchFailure(RuntimeError): pass

def search(author=None, title=None, etextnr=None, pageno=0):
    """
    Search for an etext in the Project Gutenberg catalog

    :Returns:
        list of (etext_id, authors, title, language)
    """
    if not author:
        author = ''
    if not title:
        # NB. space switches to better Gutenberg search output
        title = ' '
    if not etextnr:
        etextnr = ''

    data = _urllib.urlencode([('author', unicode(author)),
                              ('title', unicode(title)),
                              ('etextnr', unicode(etextnr)),
                              ('pageno', unicode(pageno))])
    url = _SEARCH_URL + '?' + data

    output = _fetch_page(url)
    return _parse_gutenberg_search_html(output)

def etext_info(etext_id):
    """
    Get info concerning an Etext in the Project Gutenberg catalog

    :Returns:
        list of (url, format, encoding, compression)
    """
    output = _fetch_page(_ETEXT_URL % dict(etext=etext_id))
    return _parse_gutenberg_ebook_html(etext_id, output)

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

_TAG_RE = _re.compile("<[^>]+>")

def _fetch_page(url):
    h = _urllib.urlopen(url)
    try:
        output = h.read()
    finally:
        h.close()

    if '404 not found' in output.lower():
        raise SearchFailure()

    return output
    

def _strip_tags(snippet):
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
  <td>.*?</td>
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

            entries.append((
                etext,
                unicode(_strip_tags(g.get('authors', '')), 'utf-8'),
                unicode(_strip_tags(g.get('title', '')), 'utf-8'),
                unicode(_strip_tags(g.get('language', '')), 'utf-8'),
                ))
        else:
            break

    return entries

#-- Ebook info page

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
    
    h = html
    while h:
        m = _GUTEN_ETEXT_RE_1.search(h)
        if m:
            h = h[m.end():]
            g = m.groupdict()

            url = g.get('url', '').strip()
            format = g.get('format', '').lower().strip()
            encoding = g.get('encoding', '').lower().strip()
            compression = g.get('compression', '').lower().strip()

            if url:
                if url.startswith('/'):
                    url = _DOWNLOAD_URL_BASE + url
                entries.append((url, format, encoding, compression))

        else:
            break

    return entries
