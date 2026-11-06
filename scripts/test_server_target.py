"""Security and compatibility checks for private deployment targets."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server_target


class ServerTargetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.target = Path(self.temp.name) / 'target.json'
        self.target_patch = patch.object(server_target, 'TARGET', self.target)
        self.target_patch.start()
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.target_patch.stop)
        self.addCleanup(self.env_patch.stop)

    def test_missing_configuration_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'host'):
            server_target.load_target(required=('host',))

    def test_environment_overrides_local_config(self):
        self.target.write_text(json.dumps({'host': 'local.example'}), encoding='utf-8')
        with patch.dict(os.environ, {'YOUZHIHUI_SERVER_HOST': 'env.example'}):
            self.assertEqual(server_target.load_target()['host'], 'env.example')

    def test_shell_metacharacters_and_parent_paths_rejected(self):
        for field, value in [('host', 'host;echo-bad'), ('ssh_user', 'user;id'),
                             ('base_dir', '/srv/../etc')]:
            with self.subTest(field=field):
                self.target.write_text(json.dumps({field: value}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    server_target.load_target()

    def test_origin_requires_https_without_credentials_or_path(self):
        for origin in ['http://example.com', 'https://user:pass@example.com',
                       'https://example.com/path', 'https://example.com/?q=1']:
            with self.subTest(origin=origin):
                self.target.write_text(json.dumps({'origin': origin}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    server_target.load_target()
        self.target.write_text(json.dumps({'origin': 'https://example.com/'}), encoding='utf-8')
        self.assertEqual(server_target.load_target()['origin'], 'https://example.com')


if __name__ == '__main__':
    unittest.main()
