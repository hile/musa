
import os
import re
import unittest
from musa import tree

TEST_FILE_PATHS = {
    'load_tests': [
        'foo/bar/baz.m4a',
        'foo/bar/baz.txt',
        'foo/bar/baz.mp3',
        'foo/mp3/flac mp3 aac test file.invalid',
    ],
    'name_tests': [
        '01 Test Name.m4a',
        '01 Test Name.mp3',
        '01 Tracknumber For Text File.txt',
        'No Tracknumber.ogg',
        'Test Name/02 Another Test.flac',
        '01 Test Name/No Tracknumber.flac',
        '01 Test Name/No Tracknumber Text.txt',
        'Test Name/01 Tracknumber for Text File.txt',
    ],
}

class tree_parsing(unittest.TestCase):

    def setUp(self,TEST_ROOT='test/data/tree'):
        self.root = TEST_ROOT
        for root, paths in TEST_FILE_PATHS.items():
            root = os.path.join(self.root, root)

            if not os.path.isdir(root):
                os.makedirs(root)

            for path in [os.path.join(root, x) for x in paths]:
                dir_path = os.path.dirname(path)

                if not os.path.isdir(dir_path):
                    os.makedirs(dir_path)

                if not os.path.isfile(path):
                    open(path,'w').write('\n')

    def tearDown(self):
        for root, paths in TEST_FILE_PATHS.items():
            root = os.path.join(self.root, root)

            for path in [os.path.join(root, x) for x in paths]:
                dir_path = os.path.dirname(path)
                if os.path.isfile(path):
                    os.unlink(path)

            for (root,dirs,files) in os.walk(root,topdown=False):
                os.rmdir(root)

            try:
                os.rmdir(self.root)
            except OSError,(ecode,emsg):
                pass

    def test_tree_items(self):
        t = tree.Tree(
            os.path.join(self.root, 'load_tests')
        )

        self.assertTrue(isinstance(t, tree.Tree))
        self.assertEquals(len(t), 2)

        for track in t:
            self.assertTrue(isinstance(track, tree.Track))
            self.assertTrue(os.path.isfile(track.path))

        for entry in t.files:
            self.assertTrue(isinstance(entry, tuple))
            self.assertEquals(len(entry), 2)
            self.assertTrue(os.path.isfile(os.path.join(entry[0], entry[1])))

    def test_tree_file_count(self):
        # Count music files in tree
        t = tree.Tree(
            os.path.join(self.root, 'load_tests')
        )

        tracks = len(t)
        expected = 2
        self.assertEquals(
            tracks,
            expected,
            'Invalid number of music files in test tree: {0}!={1}'.format(tracks,expected),
        )

        tracks = len(t)
        expected = 2
        self.assertEquals(
            tracks,
            expected,
            'Invalid count after explicit tree reload: {0}!={1}'.format(tracks,expected),
        )

    def test_tree_filter_regexp(self):
        t = tree.Tree(
            os.path.join(self.root, 'name_tests')
        )
        re_test = re.compile('^[0-9]+\s+.*$')

        matches = t.filter_tracks(re_test, re_path=False, re_file=True)
        expected = 3
        self.assertEquals(len(matches), expected)

        for f in matches:
            self.assertTrue(isinstance(f, tuple))
        matches = t.filter_tracks(re_test, re_path=False, re_file=True, as_tracks=True)

        expected = 3
        for f in matches:
            self.assertTrue(isinstance(f, tree.Track))

        expected = 0
        matches = t.filter_tracks(re_test, re_path=True, re_file=False)
        self.assertEquals(len(matches), expected)

        re_test = re.compile('^.*/[0-9]+\s+.*$')
        matches = t.filter_tracks(re_test, re_path=False, re_file=True)
        expected = 0
        self.assertEquals(len(matches), expected)

        expected = 1
        matches = t.filter_tracks(re_test, re_path=True, re_file=False)
        self.assertEquals(len(matches),expected)

suite = unittest.TestLoader().loadTestsFromTestCase(tree_parsing)

