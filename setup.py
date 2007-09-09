#!/usr/bin/env python
from setuptools import setup, find_packages
import subprocess, os

mod = __import__('gutenbrowse/__init__')
version = mod.__version__

if 'dev' in version:
    if os.path.exists('.hg'):
        def hg(args):
            out = subprocess.Popen(['hg'] + args, stdout=subprocess.PIPE)
            return out.communicate()[0]
        
        try:
            cur_id = hg(["id"]).split()[0]
            v = hg(["log", "--template={rev}.{node|short}",
                    "-r", cur_id.replace('+', '')])
            if '+' in cur_id:
                v  = v.replace('.', 'x.')
        except OSError:
            v += "0.XXXXXXXXXXXX"
        version += "." + v

setup(
    name = 'gutenbrowse',
    version = version,
    author = "Pauli Virtanen",
    author_email = "pav@iki.fi",
    license = "BSD, 3-clause",
    ##
    packages = find_packages(),
    scripts = ["gutenbrowse/gutenbrowse"],
    test_suite = 'nose.collector',
)
