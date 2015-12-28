
import os
import re
import unittest

from musa.models import Codec
from musa.config import MusaConfigDB
from musa.formats import MusaFileFormat, filter_available_command_list, match_codec


class test_codecs(unittest.TestCase):
    def test_codec_config_keys(self):
        db = MusaConfigDB()

        for name in db.codecs.keys():
            self.assertIsInstance(match_codec(name), Codec)
            self.assertEquals(name, match_codec(name).name)

        for name, codec in db.codecs.items():
            if 'extensions' not in codec.extensions:
                continue

            for ext in codec['extensions']:
                self.assertEquals(name, match_codec(ext).name)

    def test_fileformat_loader(self):
        db = MusaConfigDB()
        for name in db.codecs.keys():
            testpath = os.path.join('/tmp/test.{0}'.format(name))

            musaformat = MusaFileFormat(testpath)
            self.assertEquals(name, musaformat.codec.name)
            self.assertIsInstance(musaformat.get_available_encoders(), list)
            self.assertIsInstance(musaformat.get_available_decoders(), list)

        self.assertEquals(MusaFileFormat('/etc/passwd').codec, None)


suite = unittest.TestLoader().loadTestsFromTestCase(test_codecs)
