
import os,re
import unittest
from musa.formats import CODECS,MusaFileFormat,filter_available_command_list,match_codec

class test_codecs(unittest.TestCase):
    def test_codec_config_type(self):
        self.assertIsInstance(CODECS,dict)

    def test_codec_config_keys(self):
        for k in CODECS.keys():
            self.assertEquals(k,match_codec(k))

        for k,v in CODECS.items():
            if 'extensions' not in v:
                continue
            for ext in v['extensions']:
                self.assertEquals(k,match_codec(ext))

    def test_fileformat_loader(self):
        for k in CODECS.keys():
            testpath = os.path.join('/tmp/test.%s' % k)
            musaformat = MusaFileFormat(testpath)
            self.assertEquals(musaformat.codec,k)
            self.assertIsInstance(musaformat.get_available_encoders(),list)
            self.assertIsInstance(musaformat.get_available_decoders(),list)

        self.assertEquals(MusaFileFormat('/etc/passwd').codec,None)


suite = unittest.TestLoader().loadTestsFromTestCase(test_codecs)
