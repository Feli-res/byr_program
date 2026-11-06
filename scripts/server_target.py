"""Load deployment identifiers from ignored local configuration or environment."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '.local/server-target.json'


def load_target(required=()):
    data = json.loads(TARGET.read_text(encoding='utf-8-sig')) if TARGET.is_file() else {}
    names = {'host': 'YOUZHIHUI_SERVER_HOST', 'ssh_user': 'YOUZHIHUI_SSH_USER',
             'base_dir': 'YOUZHIHUI_BASE', 'origin': 'YOUZHIHUI_ORIGIN'}
    for key, env in names.items():
        if os.environ.get(env):
            data[key] = os.environ[env]
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key]]
    if missing:
        raise ValueError('Missing private server target fields: ' + ', '.join(missing))
    if data.get('host') and not re.fullmatch(r'[A-Za-z0-9.:-]+', data['host']):
        raise ValueError('Invalid server host')
    if data.get('ssh_user') and not re.fullmatch(r'[a-z_][a-z0-9_-]*\$?', data['ssh_user']):
        raise ValueError('Invalid SSH user')
    if data.get('base_dir'):
        base = data['base_dir']
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+', base) or '..' in Path(base).parts or base == '/':
            raise ValueError('Invalid server base directory')
        data['base_dir'] = base.rstrip('/')
    if data.get('origin'):
        parts = urlsplit(data['origin'])
        if parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
            raise ValueError('Origin must be a plain HTTPS origin')
        data['origin'] = data['origin'].rstrip('/')
    return data
