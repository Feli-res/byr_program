"""Create a reviewable course source bundle from current workspace, including uncommitted work."""
import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local/final412-delivery'
OMIT = {'.git', '.local', 'node_modules', '.next', 'target', '__pycache__',
        'playwright-report', 'test-results'}
TOP_FILES = ['README.md', 'Cargo.toml', 'Cargo.lock', 'rust-toolchain.toml',
             '.dockerignore', '.gitattributes', '.gitignore',
             '.upstream/README.md',
             '邮智汇_程设项目计划书.md', '邮智汇_服务器使用说明.md', '邮智汇_当前成果汇报.md']
TOP_DIRS = ['apps', 'services', 'migrations', 'deploy', 'scripts', 'docs', 'demand', '.github', 'archive', 'checks']


def files():
    for name in TOP_FILES:
        yield ROOT / name
    for name in TOP_DIRS:
        for folder, dirs, names in os.walk(ROOT / name, followlinks=False):
            dirs[:] = [d for d in dirs if d not in OMIT and not (Path(folder)/d).is_symlink()]
            for name in sorted(names):
                path = Path(folder) / name
                if path.is_symlink() or path.name.startswith('~$') or path.suffix in ('.pyc', '.log'):
                    continue
                if '.env' in name and not name.endswith('.example'):
                    continue
                if path.suffix.lower() in ('.pem', '.key', '.p12', '.pfx', '.bak') or path.name.lower().endswith('.sql.gz'):
                    continue
                if path.relative_to(ROOT).parts[0] == 'demand' and path.suffix.lower() in ('.docx', '.zip'):
                    continue
                yield path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(),
                'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'source': 'current workspace including uncommitted changes',
                'acceptance_status': 'See docs/final/README.md; server restore is not implied by packaging',
                'omitted': ['private settings/passwords/backups', 'dependency/build/cache directories', '.upstream reference repositories'],
                'files': {}}
    archive = OUT / 'youzhihui-course-source.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(files())):
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            # Prevent accidental inclusion of private key material.
            if any(marker in data for marker in (b'-----BEGIN ' + b'OPENSSH PRIVATE KEY-----', b'-----BEGIN ' + b'RSA PRIVATE KEY-----')):
                raise RuntimeError('Private key material detected in ' + rel)
            manifest['files'][rel] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            bundle.writestr(rel, data)
        bundle.writestr('DELIVERY-MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        for name, expected in manifest['files'].items():
            assert hashlib.sha256(bundle.read(name)).hexdigest() == expected['sha256']
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / 'SHA256SUMS').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'files': len(manifest['files']), 'bytes': archive.stat().st_size, 'sha256': digest}))


if __name__ == '__main__':
    main()
