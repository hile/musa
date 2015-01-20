#!/usr/bin/env python

import os,glob
from setuptools import setup, find_packages

VERSION='3.4.0'

setup(
    name = 'musa',
    version = VERSION,
    license = 'PSF',
    author = 'Ilkka Tuohela',
    author_email = 'hile@iki.fi',
    description = 'Module for music tagging and library management',
    keywords = 'music library tag management',
    url = 'http://tuohela.net/packages/musa',
    packages = ( 'musa', ),
    package_data = { '': [ '*.md', '*.txt' ] },
    scripts = glob.glob('bin/*'),
    install_requires = ( 
        'configobj', 
        'soundforest>=3.4.0', 
    ),
)

