
import glob
from setuptools import setup, find_packages
from musa import __version__

setup(
    name = 'musa',
    version = __version__,
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
<<<<<<< HEAD
        'soundforest>=3.7.0',
=======
        'soundforest>=3.6.1',
>>>>>>> 82abf027e4fffb71d75c3c85858c8a8f13735481
    ),
)

