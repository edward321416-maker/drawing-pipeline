"""Small synthetic tests of the upload preflight, never a claim of browser image edit."""
from __future__ import annotations
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.t14p.prepare_uploads import prepare_one


class UploadPreparationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.src = self.base / 'source.png'
        Image.new('RGB', (320, 180), (57, 89, 132)).save(self.src)
        self.sha = hashlib.sha256(self.src.read_bytes()).hexdigest()
        self.dest = self.base / 'upload.jpg'

    def test_source_sha_verified_and_jpeg_saved(self):
        result = prepare_one(self.src, self.sha, self.dest, 1_000_000)
        self.assertTrue(self.dest.exists())
        self.assertEqual(result['source_sha256'], self.sha)
        self.assertEqual(result['upload_pixels'], [320, 180])
        self.assertFalse(result['print_master'])
        self.assertEqual(result['status'], 'UPLOAD_READY_NOT_GPT_EDITED')

    def test_source_unchanged(self):
        before = self.src.read_bytes()
        prepare_one(self.src, self.sha, self.dest, 1_000_000)
        self.assertEqual(before, self.src.read_bytes())

    def test_mismatched_sha_rejected(self):
        with self.assertRaises(ValueError):
            prepare_one(self.src, '0' * 64, self.dest)
        self.assertFalse(self.dest.exists())

    def test_missing_file_rejected(self):
        with self.assertRaises(FileNotFoundError):
            prepare_one(self.base / 'missing.png', self.sha, self.dest)

    def test_existing_output_not_overwritten(self):
        self.dest.write_bytes(b'preserved')
        with self.assertRaises(FileExistsError):
            prepare_one(self.src, self.sha, self.dest)
        self.assertEqual(self.dest.read_bytes(), b'preserved')

    def test_invalid_size_limit_rejected(self):
        with self.assertRaises(ValueError):
            prepare_one(self.src, self.sha, self.dest, 900)


if __name__ == '__main__':
    unittest.main()
