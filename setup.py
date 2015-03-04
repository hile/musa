#!/usr/bin/env python

import glob
from setuptools import setup, find_packages

VERSION='3.4.2'

setup(
    name = 'musa',
    version = VERSION,
    license = 'PSF',
    author = 'Ilkka Tuohela',
    author_email = 'hile@iki.fi',
    description = 'Module for music tagging and library management',
    keywords = 'music library tag management',
    url = 'https://github.com/hile/musa',
    package_data = { '': [ '*.md', '*.txt' ] },
    scripts = glob.glob('bin/*'),
    packages = find_packages(),
    install_requires = ( 
        'configobj', 
        'soundforest>=3.4.4', 
    ),
)

