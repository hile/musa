"""
Tagging utilities for file formats in soundforest.

Includes
"""

__all__ = ['albumart','constants','formats','xml']

class TagError(Exception):
    """
    Exceptions raised by tag processing
    """
    def __str__(self):
        return self.args[0]

