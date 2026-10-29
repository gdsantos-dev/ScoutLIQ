"""Verify full and incremental ZIPs in disposable copies of the original source."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

from apply_release_patch import safe
from build_release import runtime_file


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(archive, target):
    target.mkdir(parents=True)
    with ZipFile(archive) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            destination = safe(target.resolve(), info.filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read(info))


def run_patch(package, target, apply=False):
    command = [sys.executable, str(package / 'apply_release_patch.py'), '--target', str(target)]
    if apply:
        command.append('--apply')
    return subprocess.run(command, capture_output=True, text=True)


def snapshot(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--release', type=Path, default=Path('release'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = json.loads((root / 'frontend/package.json').read_text(encoding='utf-8'))['version']
    with ZipFile(args.base) as source:
        base_version = json.loads(source.read('ScoutLIQ/frontend/package.json'))['version']
    artifacts = root / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='release-validation-', dir=artifacts)).resolve()
    full_zip = args.release / f'ScoutLIQ-v{version}-full-source.zip'
    patch_zip = args.release / f'ScoutLIQ-v{base_version}-to-v{version}-patch.zip'
    extract(full_zip, work / 'full')
    full = work / 'full/ScoutLIQ'
    manifest = json.loads((full / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
    assert all(sha(safe(full, name)) == value for name, value in manifest.items())
    assert set(snapshot(full)) == set(manifest) | {'RELEASE-MANIFEST.json'}
    assert not any(runtime_file(name) for name in manifest)

    backend_count = 0
    reviewed=json.loads((full/'docs/REVIEWED-ENGINE-CHANGES-v1.37.json').read_text(encoding='utf-8'))
    with ZipFile(args.base) as original:
        for info in original.infolist():
            name=info.filename.removeprefix('ScoutLIQ/')
            if not info.is_dir() and name.startswith(('backend/','migrations/')):
                if name in reviewed:
                    assert sha(full/name)==reviewed[name], 'Reviewed adaptation mismatch: '+name
                else:
                    assert (full/name).read_bytes()==original.read(info), 'Unreviewed backend change: '+name
                    backend_count+=1
    from verify_score_baseline import verify
    score_equivalence=verify(args.base)

    extract(patch_zip, work / 'patch')
    package = work / 'patch'
    plan = json.loads((package / 'PATCH-MANIFEST.json').read_text(encoding='utf-8'))
    assert plan['base_archive_sha256'] == sha(args.base)
    assert not any(runtime_file(entry['path']) for entry in plan['changes'])
    extract(args.base, work / 'installation')
    target = work / 'installation/ScoutLIQ'
    runtime = {'.env': b'LOCAL_ONLY=synthetic-preservation-test', 'data/app.db': b'synthetic-database', 'frontend/tsconfig.tsbuildinfo': b'locally-regenerated-build-cache'}
    for name, content in runtime.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    before = snapshot(target)
    checked = run_patch(package, target)
    assert checked.returncode == 0, checked.stderr
    assert snapshot(target) == before
    applied = run_patch(package, target, apply=True)
    assert applied.returncode == 0, applied.stderr
    assert all(sha(safe(target, name)) == value for name, value in manifest.items())
    assert all((target / name).read_bytes() == value for name, value in runtime.items())
    for entry in plan['changes']:
        if entry['after_sha256'] is None:
            assert not safe(target, entry['path']).exists()
    backup, = (target / '.scoutliq-backups').iterdir()
    for entry in plan['changes']:
        if entry['before_sha256'] is not None:
            assert sha(safe(backup, entry['path'])) == entry['before_sha256']
    assert run_patch(package, target, apply=True).returncode != 0

    extract(args.base, work / 'custom-installation')
    custom = work / 'custom-installation/ScoutLIQ'
    changed = custom / 'frontend/src/pages/Radar.tsx'
    changed.write_bytes(changed.read_bytes() + b'\n// local customization\n')
    custom_before = snapshot(custom)
    refused = run_patch(package, custom, apply=True)
    assert refused.returncode != 0 and 'nothing changed' in refused.stderr
    assert snapshot(custom) == custom_before
    # Exercise a source rollback only inside this disposable installation.
    for entry in reversed(plan['changes']):
        destination=safe(target,entry['path'])
        if entry['before_sha256'] is None:
            destination.unlink(missing_ok=True)
        else:
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(safe(backup,entry['path']).read_bytes())
    assert all(sha(safe(target,name))==value for name,value in before.items())
    assert all((target/name).read_bytes()==value for name,value in runtime.items())
    report = {
        'version': version, 'source_files_verified': len(manifest),
        'backend_and_migration_files_unchanged': backend_count,
        'reviewed_engine_adaptations': reviewed, 'source_rollback_matches_baseline': True,
        'patch_entries_verified': len(plan['changes']),
        'dry_run_no_writes': True, 'patched_sources_match_full_release': True,
        'runtime_and_build_cache_preserved': True, 'backups_match_baseline': True,
        'reapply_refused': True, 'local_conflict_refused_without_writes': True,
        'runtime_excluded_from_archives': True,
        'default_score_equivalence': score_equivalence,
        'archive_sha256': {p.name: sha(p) for p in (full_zip, patch_zip)},
    }
    (artifacts / 'release-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(f'Isolated validation copies: {work}')


if __name__ == '__main__':
    main()
