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

__all__ = ['myurlopen']
