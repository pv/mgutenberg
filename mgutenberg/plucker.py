"""
Bare-bones support for Plucker file format.

.. [DB] http://cvs.plkr.org/docs/DBFormat.html?view=co

"""

import array
import re
import os
import sys

import zlib

DATATYPE_PHTML = 0
DATATYPE_PHTML_COMPRESSED = 1
DATATYPE_TBMP = 2
DATATYPE_TBMP_COMPRESSED = 3
DATATYPE_MAILTO = 4
DATATYPE_LINK_INDEX = 5
DATATYPE_LINKS = 6
DATATYPE_LINKS_COMPRESSED = 7
DATATYPE_BOOKMARKS = 8
DATATYPE_CATEGORY = 9
DATATYPE_METADATA = 10
DATATYPE_STYLE_SHEET = 11
DATATYPE_FONT_PAGE = 12
DATATYPE_TABLE = 13
DATATYPE_TABLE_COMPRESSED = 14
DATATYPE_COMPOSITE_IMAGE = 15
DATATYPE_PAGELIST_METADATA = 16
DATATYPE_SORTED_URL_INDEX = 17
DATATYPE_SORTED_URL = 18
DATATYPE_SORTED_URL_COMPRESSED = 19
DATATYPE_EXT_ANCHOR_INDEX = 20
DATATYPE_EXT_ANCHOR = 21
DATATYPE_EXT_ANCHOR_COMPRESSED = 22
DATATYPE_TABLE_OF_CONTENTS = 23
DATATYPE_TABLE_OF_CONTENTS_COMPRESSED = 24

DATATYPES_COMPRESSED = [
    1, 3, 7, 14, 19, 22, 24
]

class PluckerFile(object):
    DATATYPE_READERS = {}
    FONT_SPEC = {0: None,
                 1: 'h1',
                 2: 'h2',
                 3: 'h3',
                 4: 'h4',
                 5: 'h5',
                 6: 'h6',
                 7: 'b',
                 8: 'tt',
                 9: 'sub',
                 10: 'sup'}
    
    def __init__(self, filename):
        self.f = open(filename, 'r')
        self._struct_cache = {}
        self._records = []
        self._compression = None

        self._read_headers()

    def close(self):
        self.f.close()

    # -- Parsing data streams

    def __iter__(self):
        for rec_info in self._records:
            rec_type, data = self._read_record(rec_info)

            if rec_type == DATATYPE_PHTML:
                for par in data:
                    yield ('para', None)
                    for s in self._parse_phtml(par):
                        yield s

    def _parse_phtml(self, s):
        while s:
            pos = s.find('\x00')
            if pos == -1:
                yield ('text', unicode(s, 'latin1'))
                break
            elif pos >= 0:
                if pos > 0:
                    yield ('text', unicode(s[:pos], 'latin1'))
                s = s[pos+1:]

            cmd = ord(s[0])
            size = ord(s[0]) & 0x7
            #print "                 > %x %d %r" % (cmd, size, s[1:1+size])
            if cmd == 0x11:
                yield ('font', self.FONT_SPEC.get(ord(s[1]), None))
            elif cmd == 0x38:
                yield ('br', None)
            elif cmd == 0x40:
                yield ('em', True)
            elif cmd == 0x48:
                yield ('em', False)
            elif cmd == 0x60:
                yield ('under', True)
            elif cmd == 0x68:
                yield ('under', False)
            elif cmd == 0x70:
                yield ('strike', True)
            elif cmd == 0x78:
                yield ('strike', False)
            elif cmd == 0x83:
                skip_length = ord(s[1])
                x = array.array('H', s[2:4])
                if sys.byteorder == 'little':
                    x.byteswap()
                yield ('text', unichr(x[0]))
                s = s[skip_length:]
            elif cmd == 0x85:
                skip_length = ord(s[1])
                x = array.array('L', s[2:6])
                if sys.byteorder == 'little':
                    x.byteswap()
                yield ('text', unichr(x[0]))
                s = s[skip_length:]
            s = s[1+size:]

    # -- Extracting data streams from the file

    def _parse_struct(self, record):
        r = self._struct_cache.get(record, record)
        if isinstance(r, str):
            def intsplit(x):
                m = re.match('^(\d+)(.*?):(.*?)$', x)
                if m:
                    return (int(m.group(1)), m.group(2), m.group(3))
                m = re.match('^(.*?):(.*?)$', x)
                return (1, m.group(1), m.group(2))
            r = map(intsplit, record.split(','))
            self._struct_cache[record] = r
        return r

    def _read_struct(self, record):
        out = []
        for count, c, name in self._parse_struct(record):
            fmt = array.array(c)
            data = self.f.read(fmt.itemsize * count)
            if c == 'c':
                fmt = data
            elif count == 1:
                fmt.fromstring(data)
                if sys.byteorder == 'little':
                    fmt.byteswap()
                fmt = fmt.tolist()[0]
            else:
                fmt.fromstring(data)
                fmt = fmt.tolist()
            out.append((name, fmt))
        return dict(out)

    def _read_headers(self):
        hdr = self._read_struct("32c:name,H:flags,H:version,L:created,"
                                "L:modified,8B:unused1,L:app_info_offset,"
                                "L:sort_info_id,8c:magic,4B:unused2")
        if hdr['magic'] != r'DataPlkr':
            raise IOError("Not a plucker file")
        if hdr['sort_info_id'] != 0:
            raise IOError("Malformed sort info ID")
        if hdr['version'] != 1:
            raise IOError("Invalid Plucker file format version")

        record_id = self._read_struct("L:next_record_list_id,H:num_records")
        if record_id['next_record_list_id'] != 0:
            raise IOError("Malformed record ID list")

        record_info = []
        for j in xrange(record_id['num_records']):
            r = self._read_struct("L:offset,B:attrib,3c:id")
            record_info.append(r)
        r = self._read_struct("2c:pad")

        self.f.seek(record_info[0]['offset'])
        index = self._read_struct("H:uid,H:version,H:records")
        try:
            self._compression = {1: 'doc', 2: 'zlib'}[index['version']]
        except KeyError:
            raise IOError("Unsupported compression format")

        self._start_offset = record_info[0]['offset']

        if self._compression != 'zlib':
            raise IOError("Only zlib compressed files are supported")

        self._records = record_info[1:]

    def _read_record(self, info):
        self.f.seek(info['offset'])
        r = self._read_struct("H:uid,H:par,H:size,B:type,B:flags")
        callback = self.DATATYPE_READERS.get(r['type'])
        if callback:
            return callback(self, r)
        else:
            return -1, None

    def _read_raw_data(self, size, compressed):
        if size == 0:
            return ""
        if compressed:
            z = zlib.decompressobj()
            data = ""
            read_count = 0
            while read_count < size:
                block = self.f.read(min(8192, size - read_count))
                if not block:
                    break
                read_count += len(block)
                try:
                    block = z.decompress(block)
                except zlib.error, e:
                    return None
                if block:
                    data += block
                else:
                    break
            self.f.seek(-len(z.unused_data), os.SEEK_CUR)
            return data
        else:
            return self.f.read(size)

    def _read_phtml(self, rec):
        par_info = []
        for j in xrange(rec['par']):
            par_info.append(self._read_struct("H:size,H:attributes"))
        compressed = (rec['type'] in DATATYPES_COMPRESSED)
        par_data = self._read_raw_data(rec['size'], compressed)
        par = []
        pos = 0
        for p in par_info:
            par.append(par_data[pos:pos+p['size']])
            pos += p['size']
        return (DATATYPE_PHTML, par)
    DATATYPE_READERS[DATATYPE_PHTML] = _read_phtml
    DATATYPE_READERS[DATATYPE_PHTML_COMPRESSED] = _read_phtml

if __name__ == "__main__":
    p = PluckerFile('test.pdb')
    import time
    start = time.time()
    for cmd, data in p:
        pass
    print time.time() - start

