import array
import re
import sys

import zlib

class PluckerFile(object):
    def __init__(self, filename):
        self.f = open(filename, 'r')
        self._record_cache = {}
        self._read()

    def _parse_record(self, record):
        r = self._record_cache.get(record, record)
        if isinstance(r, str):
            def intsplit(x):
                m = re.match('^(\d+)(.*?):(.*?)$', x)
                if m:
                    return (int(m.group(1)), m.group(2), m.group(3))
                m = re.match('^(.*?):(.*?)$', x)
                return (1, m.group(1), m.group(2))
            r = map(intsplit, record.split(','))
            self._record_cache[record] = r
        return r

    def _read_record(self, record):
        out = []
        for count, c, name in self._parse_record(record):
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

    def _read(self):
        hdr = self._read_record("32c:name,H:flags,H:version,L:created,"
                                "L:modified,8B:unused1,L:app_info_offset,"
                                "L:sort_info_id,8c:magic,4B:unused2")
        if hdr['magic'] != r'DataPlkr':
            raise IOError("Not a plucker file")
        if hdr['sort_info_id'] != 0:
            raise IOError("Malformed sort info ID")
        if hdr['version'] != 1:
            raise IOError("Invalid Plucker file format version")

        record_id = self._read_record("L:next_record_list_id,H:num_records")
        if record_id['next_record_list_id'] != 0:
            raise IOError("Malformed record ID list")

        record_info = []
        for j in xrange(record_id['num_records']):
            r = self._read_record("L:offset,B:attrib,3c:id")
            record_info.append(r)

        self.f.seek(record_info[0]['offset'])
        index = self._read_record("H:uid,H:version,H:records")
        try:
            compression = {1: 'doc', 2: 'zlib'}[index['version']]
        except KeyError:
            raise IOError("Unsupported compression format")

        if compression != 'zlib':
            raise IOError("Only zlib compressed files are supported")

        records = []
        continued = False
        data = ""
        for info in record_info[1:]:
            self.f.seek(info['offset'])
            r = self._read_record("H:uid,H:par,H:size,B:type,B:flags")

            continued = bool(r['flags'] & 0x01)
            compressed = r['type'] in (1,3,7,14,19,22,24)

            if continued:
                pass

        # XXX: continue

        raise IOError("Plucker file format not yet supported.")
            

if __name__ == "__main__":
    p = PluckerFile('test.pdb')
    print p

