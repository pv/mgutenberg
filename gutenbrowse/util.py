import urllib as _urllib

class HTTPError(IOError):
    def __init__(self, code, msg, headers):
        IOError.__init__(self, 'HTTP error', code, msg, headers)
    def __str__(self):
        return "HTTP: %d %s" % (self.args[1], self.args[2])

class MyURLOpener(_urllib.FancyURLopener):
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        fp.close()
        raise HTTPError(errcode, errmsg, headers)   

_urlopener = None
def myurlopen(url, data=None, proxies=None):
    """
    As urllib.urlopen, but raises HTTPErrors on HTTP failure
    """
    global _urlopener
    if proxies is not None:
        opener = MyURLOpener(proxies=proxies)
    elif not _urlopener:
        opener = MyURLOpener()
        _urlopener = opener
    else:
        opener = _urlopener
    if data is None:
        return opener.open(url)
    else:
        return opener.open(url, data)

def unique(s, key=None):
    """
    Return unique entries in s

    :Returns:
        A sequence of unique entries of s.
        If `key` is given, return entries whose key(s) is unique.
        Order is preserved, and first of duplicate entries is picked.
    """
    
    if key is not None:
        keys = (key(x) for x in s)
    else:
        keys = s
    
    seen = {}
    s2 = []
    for x, k in zip(s, keys):
        if k in seen: continue
        seen[k] = True
        s2.append(x)
    
    return s2

__all__ = ['myurlopen', 'unique']
