"""Build a source-only release and a hash-verified patch for a supplied baseline."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = ('backend', 'migrations', 'frontend/src', 'frontend/public', 'frontend/e2e', 'scripts', 'tests', 'docs')
ROOT_FILES = ('.gitignore', '.dockerignore', '.env.example', 'Dockerfile', 'railway.toml', 'alembic.ini', 'requirements.txt', 'requirements.lock', 'requirements-dev.txt', 'README.md', 'SECURITY.md')
FRONTEND_FILES = ('package.json', 'package-lock.json', 'index.html', 'tsconfig.json', 'tsconfig.e2e.json', 'vite.config.ts', 'vitest.config.ts', 'playwright.config.ts')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def runtime_file(name):
    path = PurePosixPath(name)
    return (
        any(part in {'__pycache__', 'node_modules', '.git', '.venv', 'dist', 'data', 'artifacts', 'release', '.scoutliq-backups'} for part in path.parts)
        or path.suffix in {'.pyc', '.db', '.log', '.tsbuildinfo'}
        or (path.name.startswith('.env') and path.name != '.env.example')
    )

def source_files():
    paths = [ROOT / name for name in ROOT_FILES]
    paths += [ROOT / 'frontend' / name for name in FRONTEND_FILES]
    paths += list(ROOT.glob('PATCH-*.md'))
    for directory in DIRECTORIES:
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file())
    result = {}
    for path in sorted(set(paths)):
        rel = path.relative_to(ROOT).as_posix()
        if runtime_file(rel):
            continue
        if not path.is_file():
            raise ValueError(f'Missing source file: {rel}')
        result[rel] = path.read_bytes()
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, type=Path, help='Original full ZIP')
    parser.add_argument('--expected-base', default='1.36.0', help='Required baseline version')
    args = parser.parse_args()
    if digest(args.base.read_bytes())!='64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75':
        raise ValueError('The exact authorized v1.36 FULL archive is required')
    version = json.loads((ROOT / 'frontend/package.json').read_text(encoding='utf-8'))['version']
    base = {}
    with ZipFile(args.base) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            name = item.filename.removeprefix('ScoutLIQ/')
            if '\\' in name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError('Unsafe path in base archive')
            if not runtime_file(name):
                base[name] = archive.read(item)
    base_version = json.loads(base['frontend/package.json'])['version']
    if base_version != args.expected_base:
        raise ValueError(f'Patch baseline must be version {args.expected_base}')
    files = source_files()
    manifest = {name: digest(data) for name, data in files.items()}
    files['RELEASE-MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    (ROOT / 'RELEASE-MANIFEST.json').write_bytes(files['RELEASE-MANIFEST.json'])
    output = ROOT / 'release'
    output.mkdir(exist_ok=True)
    full = output / f'ScoutLIQ-v{version}-full-source.zip'
    with ZipFile(full, 'w', ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(f'ScoutLIQ/{name}', data)
    changes = []
    for name in sorted(set(files) | set(base)):
        before, after = base.get(name), files.get(name)
        if before != after:
            changes.append({'path': name, 'before_sha256': digest(before) if before is not None else None, 'after_sha256': digest(after) if after is not None else None})
    plan = {'from': base_version, 'to': version, 'base_archive_sha256': digest(args.base.read_bytes()), 'changes': changes}
    patch = output / f'ScoutLIQ-v{base_version}-to-v{version}-patch.zip'
    with ZipFile(patch, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('PATCH-MANIFEST.json', json.dumps(plan, indent=2, sort_keys=True))
        archive.write(ROOT / 'scripts/apply_release_patch.py', 'apply_release_patch.py')
        archive.write(ROOT / 'docs/INSTALL-v1.37.md', 'README.md')
        for change in changes:
            if change['after_sha256']:
                archive.writestr('files/' + change['path'], files[change['path']])
    (output / 'CHANGED-FILES.json').write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{digest(p.read_bytes())}  {p.name}\n' for p in (full, patch)), encoding='utf-8')
    print(f'{len(files)} source files; {len(changes)} patch entries. Runtime files excluded.')
    print(full)
    print(patch)

if __name__ == '__main__':
    main()
