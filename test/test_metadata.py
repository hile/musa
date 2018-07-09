
import unittest
from soundforest import metadata

ARTWORK_PREFIXES = ['albumart', 'artwork', 'album', 'front', 'back', 'cover']
ARTWORK_FORMATS = ['jpg', 'jpeg', 'png', 'gif']

VALID_PLAYLIST_NAMES = ['foo.pls', 'foo.m3u', 'foo.bar.m3u8']
INVALID_PLAYLIST_NAMES = ['.m3u', 'foo.mp3', 'foo.ogg']


class test_metadata(unittest.TestCase):

    def setUp(self):
        self.metadata = metadata.Metadata()

    def tearDown(self):
        del self.metadata

    def test_registration(self):

        class validTestClass(metadata.MetadataFileType):
            def __init__(self, path=None):
                super(validTestClass, self).__init__(path, filenames=['foo'])

        class invalidTestClass(list):
            def __init__(self):
                return

        self.metadata.add_metadata(validTestClass())
        with self.assertRaises(ValueError):
            self.metadata.add_metadata(invalidTestClass())

    def test_artwork_files(self):
        """
        Test artwork names for metadata matches
        """
        ARTWORK_NAMES = [
            '{}.{}'.format(name, ext)
            for name in ARTWORK_PREFIXES for ext in ARTWORK_FORMATS
        ]
        for name in ARTWORK_NAMES:
            m = self.metadata.match(name)
            self.assertIsNotNone(m, 'No match for artwork file {}'.format(name))
            self.assertEqual(m.description, 'Album Artwork')

    def test_playlist_files(self):
        for name in VALID_PLAYLIST_NAMES:
            m = self.metadata.match(name)
            self.assertIsNotNone(m, 'No match for playlist file {}'.format(name))
            self.assertEqual(m.description, 'm3u playlist')

        for name in INVALID_PLAYLIST_NAMES:
            m = self.metadata.match(name)
            self.assertIsNone(m, 'Invalid name matches metadata: {}'.format(name))


suite = unittest.TestLoader().loadTestsFromTestCase(test_metadata)
