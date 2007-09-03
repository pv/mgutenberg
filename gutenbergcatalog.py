import xml.etree.ElementTree as ET
import sqlite3
import re, gc

_CATALOG_SQL = """
create table etexts (
    id integer primary key,
    title text,
    language text,
    creator text
);
create table files (
    url text primary key,
    format text,
    ref integer
);
"""

NAMESPACES = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
              "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
              "xsi": "http://www.w3.org/2001/XMLSchema-instance",
              "dc": "http://purl.org/dc/elements/1.1/",
              "dcterms": "http://purl.org/dc/terms/",
              "dcmitype": "http://purl.org/dc/dcmitype/",
              "cc": "http://web.resource.org/cc/",
              "pgterms": "http://www.gutenberg.org/rdfterms/",
              "base": "http://www.gutenberg.org/feeds/catalog.rdf",
              }

def ns(x):
    m = re.match('^([a-z]+):', x)
    if m:
        return '{%s}%s' % (NAMESPACES.get(m.group(1)), x[m.end():])
    else:
        return x

class Catalog(object):

    def __init__(self, db_file):
        self.db = sqlite3.connect(db_file)

    def _re_create(self):
        c = self.db.cursor()
        for n in ['etexts', 'files']:
            try:
                c.execute('drop table %s' % n)
            except sqlite3.OperationalError:
                pass
        c.executescript(_CATALOG_SQL)
        c.close()

    def reset(self, xml_file):
        self._re_create()

        etext_tag = ns('pgterms:etext')
        file_tag = ns('pgterms:file')
        id_attrib = ns('rdf:ID')
        ref_attrib = ns('rdf:about')
        ref_tag = ns('dcterms:isFormatOf')
        resource_attrib = ns('rdf:resource')
        title_tag = ns('dc:title')
        description_tag = ns('dc:title')
        language_tag = ns('dc:language')
        creator_tag = ns('dc:creator')
        file_attrib = ns('rdf:about')
        format_tag = ns('dc:format')

        c = self.db.cursor()

        def add_etext(xmlnode):
            id = int(xmlnode.attrib[id_attrib].replace('etext', ''))
            
            n = xmlnode.find(title_tag)
            if n is None:
                n = xmlnode.find(description_tag)
            if n is not None:
                title = unicode(n.text)
            else:
                title = u''

            n = xmlnode.find(language_tag)
            if n is not None:
                language = unicode(n[0][0].text)
            else:
                language = u''

            n = xmlnode.find(creator_tag)
            if n is not None:
                creator = unicode(n.text)
            else:
                creator = u''

            c.execute(u"insert into etexts (id,title,language,creator) "
                      u"values (?, ?, ?, ?)",
                      (id, title, language, creator))

        def add_file(xmlnode):
            n = xmlnode.find(ref_tag)
            if n is not None:
                ref = n.attrib[resource_attrib]
                ref = int(ref.replace('#etext', ''))
            else:
                ref = -1
            
            format = []
            for n in xmlnode.findall(format_tag):
                format.append(unicode(n[0][0].text))
            format = u"\n".join(format)
            
            url = xmlnode.attrib[file_attrib]

            c.execute(u"insert into files (url,format,ref) "
                      u"values (?, ?, ?)",
                      (url, format, ref))

        ctx = ET.iterparse(xml_file, events=('start', 'end'))
        ctx = iter(ctx)
        event, root = ctx.next()

        for k, (event, node) in enumerate(ctx):
            if event != "end": continue
            
            if node.tag == etext_tag:
                add_etext(node)
                root.clear()
            elif node.tag == file_tag:
                add_file(node)
                root.clear()

            if k % 100000 == 0:
                self.db.commit()

        self.db.commit()
        c.close()

if __name__ == "__main__":
    c = Catalog('catalog.db')
    c.reset('catalog.rdf')
    print c
