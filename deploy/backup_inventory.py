"""Inventory a quiesced backup; includes no content, passwords, or personal data."""
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath


def database_inventory(container):
    def query(sql):
        run = subprocess.run([
            'docker', 'exec', '-e', 'SQL=' + sql, container, 'sh', '-c',
            'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" -D "$MYSQL_DATABASE" '
            '--batch --skip-column-names -e "$SQL"',
        ], capture_output=True, text=True, check=True, timeout=60)
        return run.stdout.strip()
    tables = query("SELECT TABLE_NAME FROM information_schema.tables WHERE table_schema=DATABASE() AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;").splitlines()
    if not tables or not all(re.fullmatch(r'[A-Za-z0-9_]+', table) for table in tables):
        raise RuntimeError('Unexpected database table list')
    return {table: int(query(f'SELECT COUNT(*) FROM `{table}`;')) for table in tables}


def upload_inventory(archive):
    files = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise RuntimeError('Unsafe upload archive entry')
            if member.isfile():
                name = str(path)
                if name in files:
                    raise RuntimeError('Duplicate upload archive entry')
                content = tar.extractfile(member)
                digest = hashlib.file_digest(content, 'sha256').hexdigest()
                files[name] = {'size': member.size, 'sha256': digest}
    return dict(sorted(files.items()))


if __name__ == '__main__':
    backup, container = Path(sys.argv[1]), sys.argv[2]
    inventory = {'tables': database_inventory(container),
                 'uploads': upload_inventory(backup / 'uploads.tar.gz')}
    (backup / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n', encoding='utf-8')
