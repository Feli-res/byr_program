"""Safety checks for backup import: corruption, omissions and unsafe tar entries."""
import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))
from backup_inventory import upload_inventory
from restore412 import checksum_snapshot
from server412 import verify_offsite


class BackupSafety(unittest.TestCase):
    def test_upload_bytes_and_empty_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'uploads.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                item = tarfile.TarInfo('./empty')
                item.type = tarfile.DIRTYPE
                tar.addfile(item)
                item = tarfile.TarInfo('./nested/picture.png')
                item.size = 5
                tar.addfile(item, io.BytesIO(b'image'))
            actual = upload_inventory(archive)
            self.assertEqual(actual, {'nested/picture.png': {'size': 5, 'sha256': hashlib.sha256(b'image').hexdigest()}})

    def test_unsafe_archive_cannot_be_imported(self):
        with tempfile.TemporaryDirectory() as temp:
            for name, kind in (('../outside', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                               ('link', tarfile.SYMTYPE), ('hardlink', tarfile.LNKTYPE)):
                with self.subTest(name=name):
                    archive = Path(temp) / 'uploads.tar.gz'
                    with tarfile.open(archive, 'w:gz') as tar:
                        item = tarfile.TarInfo(name)
                        item.type = kind
                        item.linkname = '../../outside'
                        tar.addfile(item)
                    with self.assertRaises(RuntimeError):
                        upload_inventory(archive)

    def test_checksum_corruption_and_missing_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            names = ['database.sql', 'uploads.tar.gz', 'server.env', 'release.txt', 'inventory.json']
            lines = []
            for name in names:
                (root / name).write_bytes(b'original')
                lines.append(hashlib.sha256(b'original').hexdigest() + '  ' + name)
            (root / 'SHA256SUMS').write_text('\n'.join(lines))
            self.assertEqual(len(checksum_snapshot(root)), 5)
            (root / 'database.sql').write_bytes(b'corrupted')
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                checksum_snapshot(root)
            (root / 'database.sql').write_bytes(b'original')
            (root / 'SHA256SUMS').write_text('\n'.join(lines[:-1]))
            with self.assertRaisesRegex(RuntimeError, 'inventory'):
                checksum_snapshot(root)

    def test_checksum_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'SHA256SUMS').write_text('0'*64 + '  ../outside\n')
            with self.assertRaisesRegex(RuntimeError, 'Unexpected checksum'):
                checksum_snapshot(root)

    def test_offsite_download_checks_every_component(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'offsite.tar.gz'
            snapshot = '20261105T080000Z'
            names = ['database.sql', 'uploads.tar.gz', 'server.env', 'release.txt', 'inventory.json']
            checksums = '\n'.join(hashlib.sha256(b'content').hexdigest()+'  '+name for name in names).encode()
            for corrupt in (False, True):
                with self.subTest(corrupt=corrupt):
                    with tarfile.open(archive, 'w:gz') as tar:
                        for name in [*names, 'SHA256SUMS']:
                            content = checksums if name == 'SHA256SUMS' else b'content'
                            if corrupt and name == 'database.sql':
                                content = b'changed'
                            item = tarfile.TarInfo(snapshot + '/' + name)
                            item.size = len(content)
                            tar.addfile(item, io.BytesIO(content))
                    if corrupt:
                        with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                            verify_offsite(archive, snapshot)
                    else:
                        self.assertEqual(len(verify_offsite(archive, snapshot)), 5)


if __name__ == '__main__':
    unittest.main()
