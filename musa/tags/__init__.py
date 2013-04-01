# coding=utf-8
"""Tag processing

Audio file tag, albumart and tag output processing classes

"""

__all__ = ['albumart','constants','formats','xmltag']

class TagError(Exception):
    """
    Exceptions raised by tag processing
    """
    def __str__(self):
        return self.args[0]

