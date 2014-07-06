#!/usr/bin/env python

import os,glob
from setuptools import setup,find_packages

VERSION='3.1'
README = open(os.path.join(os.path.dirname(__file__),'README.md'),'r').read()

setup(
    name = 'musa',
    version = VERSION,
    license = 'PSF',
    author = 'Ilkka Tuohela',
    author_email = 'hile@iki.fi',
    description = 'Module for music tagging and library management',
    long_description = README,
    keywords = 'music library tag management',
    url = 'http://tuohela.net/packages/musa',
    zip_safe = False,
    packages = ( 'musa', ),
    scripts = glob.glob('bin/*'),
    install_requires = ( 
        'configobj', 
        'soundforest>=3.2', 
    ),
)

