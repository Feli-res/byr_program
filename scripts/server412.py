"""Pinned-host SSH operations for final delivery. Secrets stay under .local.

Set YOUSHIZHUI_SSH_PASSWORD or put a single password line in
.local/ssh-password.txt. This is separate from application demo credentials.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/deploy-tools'))
import paramiko
from server_target import load_target

WORK = ROOT / '.local/final412-server'


def source_files(path, omitted):
    if path.is_file():
        yield path
        return
    for folder, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in omitted]
        for name in files:
            yield Path(folder) / name


def verify_offsite(archive, snapshot):
    with tarfile.open(archive, 'r:gz') as tar:
        members = {}
        allowed = {'SHA256SUMS', 'database.sql', 'uploads.tar.gz', 'server.env', 'release.txt', 'inventory.json'}
        for member in tar.getmembers():
            if member.isdir() and member.name.rstrip('/') == snapshot:
                continue
            prefix = snapshot + '/'
            name = member.name.removeprefix(prefix)
            if not member.name.startswith(prefix) or name not in allowed or not member.isfile() or name in members:
                raise RuntimeError('Unexpected offsite archive entry')
            members[name] = member
        if set(members) != allowed:
            raise RuntimeError('Incomplete offsite archive')
        expected = {}
        for line in tar.extractfile(members['SHA256SUMS']).read().decode('ascii').splitlines():
            digest, name = line.split(maxsplit=1)
            name = name.lstrip('* ')
            if name in expected or name not in allowed - {'SHA256SUMS'}:
                raise RuntimeError('Unexpected offsite checksum entry')
            expected[name] = digest
        if set(expected) != allowed - {'SHA256SUMS'}:
            raise RuntimeError('Missing offsite checksum')
        for name, digest in expected.items():
            if hashlib.file_digest(tar.extractfile(members[name]), 'sha256').hexdigest() != digest:
                raise RuntimeError('Offsite checksum mismatch: ' + name)
    return expected


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'deploy', 'backup', 'restore', 'download'])
    parser.add_argument('--snapshot', help='UTC backup directory name, required by restore/download')
    parser.add_argument('--tag', help='New release folder name, required by deploy')
    args = parser.parse_args()
    if args.action == 'deploy' and (not args.tag or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', args.tag)):
        parser.error('deploy requires --tag with a valid new release name')
    TAG = args.tag
    try:
        target = load_target(('host', 'ssh_user', 'base_dir'))
    except ValueError as error:
        raise SystemExit(str(error) + '; configure .local/server-target.json') from None
    BASE = target['base_dir']
    password = os.environ.get('YOUSHIZHUI_SSH_PASSWORD')
    private = ROOT / '.local/ssh-password.txt'
    if not password and private.is_file():
        password = private.read_text(encoding='utf-8-sig').strip()
    if not password:
        raise SystemExit('Missing SSH password: configure .local/ssh-password.txt or YOUSHIZHUI_SSH_PASSWORD')
    WORK.mkdir(parents=True, exist_ok=True)
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(str(ROOT / '.local/server-known-hosts'))
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(target['host'], username=target['ssh_user'], password=password,
                look_for_keys=False, allow_agent=False, timeout=25)

    def run(command, sudo=False, timeout=300):
        if sudo:
            command = 'sudo -S -p "" bash -c ' + shlex.quote(command)
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        if sudo:
            stdin.write(password + '\n')
            stdin.flush()
            stdin.channel.shutdown_write()
        # Drain both streams so a full stderr buffer cannot deadlock a build.
        channel = stdout.channel
        import time
        deadline = time.monotonic() + timeout
        out, err = bytearray(), bytearray()
        while not channel.exit_status_ready() or channel.recv_ready() or channel.recv_stderr_ready():
            if time.monotonic() > deadline:
                channel.close()
                raise TimeoutError('Remote operation timed out; inspect its server process before retrying')
            if channel.recv_ready():
                data = channel.recv(65536)
                out.extend(data)
                print(data.decode('utf-8', 'replace'), end='', flush=True)
            if channel.recv_stderr_ready():
                data = channel.recv_stderr(65536)
                err.extend(data)
                print(data.decode('utf-8', 'replace'), end='', file=sys.stderr, flush=True)
            time.sleep(.1)
        code = channel.recv_exit_status()
        (WORK / (args.action + '.log')).write_bytes(bytes(out) + bytes(err))
        if code:
            raise RuntimeError('Remote operation failed: ' + str(code))

    try:
        if args.action == 'inspect':
            run(f'set -e; readlink -f {BASE}/current; docker ps --format "{{{{.Names}}}} {{{{.Status}}}}"; free -m; df -h {BASE}; systemctl is-enabled docker youzhihui-backup.timer; systemctl list-timers youzhihui-backup.timer --no-pager', sudo=True)
        elif args.action == 'deploy':
            # A fresh release only. Never removes or overwrites an existing release.
            archive = WORK / 'release.tar.gz'
            omitted = {'node_modules', '.next', 'target', '__pycache__', '.git'}
            with tarfile.open(archive, 'w:gz') as tar:
                paths = [ROOT / name for name in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml', '.dockerignore', 'services/api', 'apps/web', 'migrations', 'deploy')]
                for path in paths:
                    for item in source_files(path, omitted):
                        rel = item.relative_to(ROOT)
                        if item.is_symlink() or not item.is_file() or any(p in omitted for p in rel.parts):
                            continue
                        if '.env' in item.name and not item.name.endswith('.example'):
                            continue
                        tar.add(item, arcname=rel.as_posix(), recursive=False)
            sftp = ssh.open_sftp()
            sftp.put(str(archive), BASE + '/releases/' + TAG + '.tar.gz')
            sftp.close()
            run(f'set -e; test ! -e {BASE}/releases/{TAG}; mkdir {BASE}/releases/{TAG}; tar -xzf {BASE}/releases/{TAG}.tar.gz -C {BASE}/releases/{TAG}; ln -s {BASE}/shared/.env.prod {BASE}/releases/{TAG}/deploy/.env.prod')
            # Install helper with the backup script as a pair; preserve older scripts.
            run(f'set -e; cp -n {BASE}/shared/backup.sh {BASE}/shared/backup.before412.sh; install -m 700 {BASE}/releases/{TAG}/deploy/backup_inventory.py {BASE}/shared/backup_inventory.py; install -m 700 {BASE}/releases/{TAG}/deploy/backup.sh {BASE}/shared/backup.sh; {BASE}/shared/update.sh {TAG}', sudo=True, timeout=3600)
        elif args.action == 'backup':
            run(f'{BASE}/shared/backup.sh', sudo=True)
        else:
            if not args.snapshot or not re.fullmatch(r'\d{8}T\d{6}Z', args.snapshot):
                parser.error('--snapshot must be a UTC backup directory name')
            snapshot = BASE + '/backups/' + args.snapshot
            if args.action == 'restore':
                # Use the exact local restore tooling alongside the matching release.
                run(f'mkdir -p {BASE}/final412-tools/scripts {BASE}/final412-tools/deploy')
                sftp = ssh.open_sftp()
                for local, remote in [('scripts/restore412.py', 'scripts/restore412.py'),
                                      ('scripts/server_target.py', 'scripts/server_target.py'),
                                      ('deploy/backup_inventory.py', 'deploy/backup_inventory.py'),
                                      ('deploy/compose.restore412.yaml', 'deploy/compose.restore412.yaml'),
                                      ('deploy/nginx.411.conf', 'deploy/nginx.411.conf')]:
                    sftp.put(str(ROOT / local), BASE + '/final412-tools/' + remote)
                sftp.close()
                run(f'YOUZHIHUI_BASE={shlex.quote(BASE)} python3 {BASE}/final412-tools/scripts/restore412.py {snapshot}', sudo=True, timeout=900)
            else:
                remote = BASE + '/shared/final412-offsite.tar.gz'
                run(f'set -e; cd {snapshot}; sha256sum -c SHA256SUMS; tar -czf {remote} -C {BASE}/backups {args.snapshot}; chown {target["ssh_user"]} {remote}; chmod 600 {remote}', sudo=True)
                sftp = ssh.open_sftp()
                sftp.get(remote, str(WORK / 'offsite-backup.tar.gz'))
                sftp.close()
                verified = verify_offsite(WORK / 'offsite-backup.tar.gz', args.snapshot)
                (WORK / 'offsite-verification.json').write_text(json.dumps({'snapshot': args.snapshot, 'status': 'passed', 'checksums': verified}, indent=2) + '\n')
                print('Downloaded and verified every backup checksum: .local/final412-server/offsite-backup.tar.gz')
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
