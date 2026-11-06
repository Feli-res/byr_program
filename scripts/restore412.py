"""Restore a full snapshot into a NEW isolated Compose project on the Linux server.

Run as root. Never imports into trial, never removes a volume, never exposes a
public listener. Leaves the restore environment running for application checks;
use --stop to stop only this project when those checks are complete.
"""
import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))
from backup_inventory import database_inventory, upload_inventory

BASE = Path('/home/sunxiang/youzhihui')
PROJECT = 'youzhihui-restore412'
WORK = BASE / 'restore412'


def run(argv, **kwargs):
    return subprocess.run(argv, check=kwargs.pop('check', True), timeout=kwargs.pop('timeout', 240), **kwargs)


def output(argv):
    return run(argv, capture_output=True, text=True).stdout.strip()


def compose(*args, **kwargs):
    return run(['docker', 'compose', '-p', PROJECT, '--env-file', str(WORK / '.env.restore'),
                '-f', str(WORK / 'compose.restore412.yaml'), *args], **kwargs)


def checksum_snapshot(snapshot):
    allowed = {'database.sql', 'uploads.tar.gz', 'server.env', 'release.txt', 'inventory.json'}
    entries = {}
    for line in (snapshot / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('* ')
        if name not in allowed or name in entries or not re.fullmatch('[a-f0-9]{64}', digest):
            raise RuntimeError('Unexpected checksum entry')
        path = snapshot / name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('Missing or unsafe backup component')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != digest:
            raise RuntimeError('Backup checksum mismatch: ' + name)
        entries[name] = actual
    if set(entries) != allowed:
        raise RuntimeError('Snapshot must include the 4.12 inventory; generate a new backup')
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', nargs='?', type=Path)
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    if os.name != 'posix' or os.geteuid() != 0:
        raise SystemExit('Run with sudo on the Linux project server')
    if args.stop:
        compose('stop')
        return
    if args.snapshot is None:
        parser.error('snapshot is required')
    snapshot = args.snapshot.resolve(strict=True)
    if snapshot.parent != (BASE / 'backups').resolve() or not re.fullmatch(r'\d{8}T\d{6}Z', snapshot.name):
        raise SystemExit('Snapshot must be a timestamp directory inside this project backups/')
    hashes = checksum_snapshot(snapshot)
    expected = json.loads((snapshot / 'inventory.json').read_text())
    if upload_inventory(snapshot / 'uploads.tar.gz') != expected['uploads']:
        raise RuntimeError('Backup upload inventory mismatch')
    release = Path((snapshot / 'release.txt').read_text().strip()).resolve(strict=True)
    if release.parent != (BASE / 'releases').resolve():
        raise RuntimeError('Release is outside this project')
    tag = release.name
    # Never reuse a prior rehearsal: no imports into a populated volume.
    prior = output(['docker', 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT])
    if prior or WORK.exists():
        raise RuntimeError('Restore project/work directory already exists; preserve it and review before another rehearsal')
    mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    if int(mem['MemAvailable'].split()[0]) < 4 * 1024 * 1024:
        raise RuntimeError('At least 4 GiB available memory is required')
    if shutil.disk_usage(BASE).free < 10 * 1024**3:
        raise RuntimeError('At least 10 GiB free disk space is required')
    output(['docker', 'volume', 'inspect', 'youzhihui-trial_embedding-cache'])
    for image in ('youzhihui-api:' + tag, 'youzhihui-web:' + tag):
        output(['docker', 'image', 'inspect', '--format', '{{.Id}}', image])
    os.umask(0o077)
    WORK.mkdir(mode=0o700)
    deploy = Path(__file__).resolve().parents[1] / 'deploy'
    for name in ('compose.restore412.yaml', 'nginx.411.conf'):
        shutil.copyfile(deploy / name, WORK / name)
    # Dedicated database identity and keys; no external text AI credential copied.
    config = {'MYSQL_DATABASE': 'youzhihui_restore412', 'MYSQL_USER': 'restore412',
              'MYSQL_PASSWORD': secrets.token_hex(24), 'MYSQL_ROOT_PASSWORD': secrets.token_hex(24),
              'AUTH_SECRET': secrets.token_hex(48), 'TRUSTED_PROXY_KEY': secrets.token_hex(32),
              'API_IMAGE': 'youzhihui-api:' + tag, 'WEB_IMAGE': 'youzhihui-web:' + tag}
    (WORK / '.env.restore').write_text(''.join(f'{k}={v}\n' for k, v in config.items()))
    result = {'stage': '4.12', 'started_at': datetime.now(timezone.utc).isoformat(),
              'snapshot': snapshot.name, 'release': tag, 'checksums': hashes,
              'project': PROJECT, 'public_listener': False, 'status': 'running'}
    try:
        compose('config', '--quiet')
        compose('up', '-d', '--wait', 'mysql', 'redis')
        mysql = output(['docker', 'compose', '-p', PROJECT, '--env-file', str(WORK / '.env.restore'),
                        '-f', str(WORK / 'compose.restore412.yaml'), 'ps', '-q', 'mysql'])
        with (snapshot / 'database.sql').open('rb') as source:
            run(['docker', 'exec', '-i', mysql, 'sh', '-c',
                 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysql -u "$MYSQL_USER" -D "$MYSQL_DATABASE"'], stdin=source)
        actual = database_inventory(mysql)
        if actual != expected['tables']:
            raise RuntimeError('Restored table row counts differ from the snapshot')
        result['table_counts'] = actual
        result['all_table_counts_match'] = True
        # Create the remaining volumes/containers without starting background tasks.
        compose('create', 'api', 'web', 'embedding', 'edge')
        with (snapshot / 'uploads.tar.gz').open('rb') as source:
            run(['docker', 'run', '--rm', '-i', '--network', 'none', '--user', '0', '--entrypoint', 'tar',
                 '-v', PROJECT + '_uploads:/data', config['API_IMAGE'], '-xzf', '-', '-C', '/data'], stdin=source)
        restored_tar = WORK / 'restored-uploads.tar.gz'
        with restored_tar.open('wb') as dest:
            run(['docker', 'run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'tar',
                 '-v', PROJECT + '_uploads:/data:ro', config['API_IMAGE'], '-czf', '-', '-C', '/data', '.'], stdout=dest)
        if upload_inventory(restored_tar) != expected['uploads']:
            raise RuntimeError('Restored upload contents differ from the snapshot')
        result['upload_files'] = len(expected['uploads'])
        result['all_upload_hashes_match'] = True
        # Copy only model files, from a read-only mount, into a fresh cache volume.
        model_cache = WORK / 'model-cache.tar'
        with model_cache.open('wb') as dest:
            run(['docker', 'run', '--rm', '--network', 'none', '--user', '0', '--entrypoint', 'tar',
                 '-v', 'youzhihui-trial_embedding-cache:/data:ro', config['API_IMAGE'], '-cf', '-', '-C', '/data', '.'], stdout=dest)
        with model_cache.open('rb') as source:
            run(['docker', 'run', '--rm', '-i', '--network', 'none', '--user', '0', '--entrypoint', 'tar',
                 '-v', PROJECT + '_embedding-cache:/data', config['API_IMAGE'], '-xf', '-', '-C', '/data'], stdin=source)
        model_cache.unlink()
        compose('up', '-d', '--wait', '--wait-timeout', '240')
        result['status'] = 'data_restored_application_checks_pending'
        print('RESTORED: all table counts and upload SHA256 hashes match; verify http://localhost:18103 before marking acceptance passed')
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = f'{type(exc).__name__}: {exc}'
        # Stop isolated writers on failure; preserve all evidence and volumes.
        compose('stop', check=False)
        raise
    finally:
        (WORK / 'restore-result.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
