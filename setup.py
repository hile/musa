
import glob
from setuptools import setup, find_packages
from musa import __version__

setup(
    name='musa',
    version=__version__,
    license='PSF',
    author='Ilkka Tuohela',
    author_email='hile@iki.fi',
    description='Soundforest module CLI for music tagging and library management',
    keywords='music library tag management',
    url='https://github.com/hile/musa',
    package_data={'': ['*.md', '*.txt']},
    scripts=glob.glob('bin/*'),
    packages=find_packages(),
    install_requires=(
        'soundforest>=4.3.3',
        'configobj',
    ),
)
