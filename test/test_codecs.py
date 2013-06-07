
import os,re
import unittest

from musa.models import Codec
from musa.config import MusaConfigDB
from musa.formats import MusaFileFormat,filter_available_command_list,match_codec


class test_codecs(unittest.TestCase):
    def test_codec_config_keys(self):
        db = MusaConfigDB()
        for k in db.codecs.keys():
            self.assertIsInstance(match_codec(k),Codec)
            self.assertEquals(k,match_codec(k).name)

        for k,v in db.codecs.items():
            if 'extensions' not in v.extensions:
                continue
            for ext in v['extensions']:
                self.assertEquals(k,match_codec(ext).name)

    def test_fileformat_loader(self):
        db = MusaConfigDB()
        for k in db.codecs.keys():
            testpath = os.path.join('/tmp/test.%s' % k)
            musaformat = MusaFileFormat(testpath)
            self.assertEquals(k,musaformat.codec.name)
            self.assertIsInstance(musaformat.get_available_encoders(),list)
            self.assertIsInstance(musaformat.get_available_decoders(),list)

        self.assertEquals(MusaFileFormat('/etc/passwd').codec,None)


suite = unittest.TestLoader().loadTestsFromTestCase(test_codecs)
