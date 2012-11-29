
Musa Music Library Management Tools

This module implements some python classes for music library management,
including command line scripts to use these tools. All code is implemented
in python under module 'musa'.

This module used to be called 'banana'. Since 'musa' is both 'music' in Finnish
and the genus of bananas, I found it appropriate to rename the module when the
trees were moved to github and code reorganized in general.

See example script in doc/musa-script.example

Using the scripts:

The scripts installed all have prefix 'musa-' in the name, including:
  musa-tags: view, edit and modify tags in supported music files
  musa-convert: transcode files between supported formats
  musa-albumart: embed or extract albumarto from and to supported formats

You should configure your music library paths in /etc/musa/paths.conf and
the codec transcoding command parameters in /etc/musa/codecs.conf. You can
also place these files to ~/.musa/ folder for personal use.

Using the classes:

See example script in doc/musa-script.example and the generic wrapper module
for scripts in musa/script.py. It is also easier to understand things when you
read the musa-tags, musa-convert and musa-albumart scripts in bin directory.

Must common classes to use are following:

musa.tree: classes Tree, Album and Song implement most required options to 
process music files, initializing all the other classes in the module

musa.transcoder: implements threaded transcoding of Tree, Album and Song
objects

musa.albumart: albumart parsing for files, usually used via Tags objects 



