#!/usr/bin/env python
from setuptools import setup, find_packages
import subprocess, os

mod = __import__('mgutenberg/__init__')
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
            v = "." + v
        except OSError:
            v = ""
        version += v

setup(
    name = 'mgutenberg',
    version = version,
    author = "Pauli Virtanen",
    author_email = "pav@iki.fi",
    license = "BSD, 3-clause",
    ##
    packages = find_packages(),
    scripts = ["mgutenberg/mgutenberg"],
    test_suite = 'nose.collector',
)
