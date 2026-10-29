"""Verify an extracted release patch; apply only with --apply after full preflight."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def safe(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
        raise ValueError(f'Invalid patch path: {name}')
    target = (root / name).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError(f'Path escapes target directory: {name}')
    return target

def atomic_copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, staging = tempfile.mkstemp(prefix='.scoutliq-', dir=target.parent)
    os.close(handle)
    try:
        shutil.copyfile(source, staging)
        os.replace(staging, target)
    finally:
        Path(staging).unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    root = args.target.resolve(strict=True)
    plan = json.loads((package / 'PATCH-MANIFEST.json').read_text(encoding='utf-8'))
    if not (root / 'backend/main.py').is_file():
        raise ValueError('Target must be the ScoutLIQ project directory')
    version = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))['version']
    if version != plan['from']:
        raise ValueError(f"Expected {plan['from']}; found {version}. No files changed.")
    conflicts, validated = [], []
    for entry in plan['changes']:
        path = safe(root, entry['path'])
        if (path.exists() and not path.is_file()) or sha(path) != entry['before_sha256']:
            conflicts.append(entry['path'])
        source = safe((package / 'files').resolve(), entry['path'])
        if entry['after_sha256'] is not None and sha(source) != entry['after_sha256']:
            raise ValueError(f"Damaged patch payload: {entry['path']}")
        validated.append((entry, path, source))
    if conflicts:
        raise ValueError('Local changes or wrong baseline; nothing changed:\n' + '\n'.join(conflicts))
    print(f"Verified {len(validated)} changes: {plan['from']} -> {plan['to']}.")
    if not args.apply:
        print('Dry run only. Stop web and research workers, back up the database, then repeat with --apply.')
        return
    backup = safe(root, '.scoutliq-backups/' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    backup.mkdir(parents=True, exist_ok=False)
    for entry, path, _ in validated:
        if entry['before_sha256'] is not None:
            destination = safe(backup, entry['path'])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    (backup / 'PATCH-MANIFEST.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    completed = []
    try:
        for entry, path, source in validated:
            if entry['after_sha256'] is None:
                path.unlink()
            else:
                atomic_copy(source, path)
            completed.append((entry,path))
    except Exception:
        for entry, path in reversed(completed):
            if entry['before_sha256'] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_copy(safe(backup,entry['path']),path)
        raise
    print(f'Source updated. Backup: {backup}')
    print('Install requirements.lock, run npm ci/build in frontend and python -m alembic upgrade head, then restart web and research worker. This patch did not change the database or .env file.')

if __name__ == '__main__':
    main()
