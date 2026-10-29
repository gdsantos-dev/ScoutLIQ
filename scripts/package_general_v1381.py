"""Package and verify the development integration against the exact integrated v1.38.0-dev FULL.

Only disposable installations are patched. Does not migrate or deploy anything.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from build_release import ROOT, source_files, digest, runtime_file
from apply_release_patch import safe

BASE_HASH = 'f66a5097486760825f3f3ba1b33c5cab7036a81bd1ce282010b414afe916232b'
VERSION = '1.38.1-dev'


def extract(archive, target):
    target.mkdir(parents=True)
    with ZipFile(archive) as z:
        for entry in z.infolist():
            if entry.is_dir():
                continue
            path = safe(target.resolve(), entry.filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(entry))


def snapshot(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in root.rglob('*') if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    args = parser.parse_args()
    assert digest(args.base.read_bytes()) == BASE_HASH, 'Wrong baseline'
    with ZipFile(args.base) as z:
        baseline = {n.removeprefix('ScoutLIQ/'): z.read(n) for n in z.namelist() if not n.endswith('/')}
    baseline_manifest = json.loads(baseline['RELEASE-MANIFEST.json'])
    assert all(digest(baseline[n]) == h for n, h in baseline_manifest.items())
    files = source_files()
    files['DEV-OVERLAY-MANIFEST.json'] = (ROOT/'DEV-OVERLAY-MANIFEST.json').read_bytes()
    assert json.loads(files['frontend/package.json'])['version'] == VERSION
    assert not any(runtime_file(n) for n in files)
    for name in ('backend/scoring.py', 'backend/commercial_fit.py', 'backend/research_worker.py',
                 'backend/absorption.py', 'backend/absorption_models.py', 'backend/main.py',
                 'frontend/src/components/AbsorptionDialog.tsx', 'frontend/src/components/absorption-dialog.css',
                 'frontend/src/App.tsx', 'frontend/src/pages/Pipeline.tsx', 'tests/test_absorption.py',
                 'tests/test_absorption_migration.py', 'frontend/e2e/absorption.spec.ts'):
        assert files[name] == baseline[name], 'Preserved engine changed: '+name
    for name in baseline:
        if name.startswith('migrations/versions/'):
            assert files[name] == baseline[name], 'Historical migration changed: '+name
    manifest = {n: digest(data) for n, data in files.items()}
    files['RELEASE-MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()
    (ROOT/'RELEASE-MANIFEST.json').write_bytes(files['RELEASE-MANIFEST.json'])
    changes = [{'path': n, 'before_sha256': digest(baseline[n]) if n in baseline else None,
                'after_sha256': digest(files[n]) if n in files else None}
               for n in sorted(set(baseline) | set(files)) if baseline.get(n) != files.get(n)]
    plan = {'from': '1.38.0-dev', 'to': VERSION, 'designation': 'v1.38.1-dev; validação local, sem homologação externa',
            'base_archive_sha256': BASE_HASH, 'changes': changes}
    output = ROOT/'release'; output.mkdir(exist_ok=True)
    full = output/'ScoutLIQ-v1.38.1-dev-FULL.zip'
    patch = output/'ScoutLIQ-v1.38.0-dev-to-v1.38.1-dev-PATCH.zip'
    with ZipFile(full, 'w', ZIP_DEFLATED) as z:
        for n, data in files.items():
            z.writestr('ScoutLIQ/'+n, data)
    with ZipFile(patch, 'w', ZIP_DEFLATED) as z:
        z.writestr('PATCH-MANIFEST.json', json.dumps(plan, indent=2))
        z.write(ROOT/'scripts/apply_release_patch.py', 'apply_release_patch.py')
        z.write(ROOT/'docs/INSTALL-v1.38.1-dev.md', 'README.md')
        for entry in changes:
            if entry['after_sha256'] is not None:
                z.writestr('files/'+entry['path'], files[entry['path']])
    work = Path(tempfile.mkdtemp(prefix='package-integration-', dir=ROOT/'artifacts')).resolve()
    extract(full, work/'full')
    assert snapshot(work/'full/ScoutLIQ') == {n: digest(b) for n, b in files.items()}
    extract(patch, work/'patch')
    extract(args.base, work/'install')
    target = work/'install/ScoutLIQ'
    runtime = {'.env': b'SYNTHETIC_PRESERVATION_ONLY=1', 'data/test.db': b'not-a-personal-database'}
    for n, data in runtime.items():
        p = target/n; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    before = snapshot(target)
    def apply(execute=False):
        return subprocess.run([sys.executable, str(work/'patch/apply_release_patch.py'),
            '--target', str(target), *(['--apply'] if execute else [])], capture_output=True, text=True)
    result = apply(); assert result.returncode == 0, result.stderr
    assert snapshot(target) == before
    # Refuse a local customization before making any writes.
    custom = target/'backend/smart_search.py'; original = custom.read_bytes()
    custom.write_bytes(original+b'\n# local change\n')
    local_before = snapshot(target)
    result = apply(True); assert result.returncode != 0
    assert snapshot(target) == local_before
    custom.write_bytes(original)
    result = apply(True); assert result.returncode == 0, result.stderr
    assert all((target/n).read_bytes() == b for n, b in files.items())
    assert all((target/n).read_bytes() == b for n, b in runtime.items())
    assert apply(True).returncode != 0
    backup, = (target/'.scoutliq-backups').iterdir()
    for entry in reversed(changes):
        p = safe(target, entry['path'])
        if entry['before_sha256'] is None:
            p.unlink(missing_ok=True)
        else:
            old = safe(backup, entry['path']).read_bytes()
            assert digest(old) == entry['before_sha256']
            p.write_bytes(old)
    assert all(digest((target/n).read_bytes()) == h for n, h in before.items())
    report = {'designation': plan['designation'], 'source_files': len(files), 'changes': changes,
              'base_sha256': BASE_HASH, 'manifest_verified': True, 'dry_run_no_writes': True,
              'conflict_refused_without_writes': True, 'patch_matches_full': True,
              'runtime_preserved': True, 'reapply_refused': True, 'source_rollback_verified': True,
              'production_ready': False,
              'sha256': {p.name: digest(p.read_bytes()) for p in (full, patch)}}
    (output/'PACKAGE-VALIDATION.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (output/'SHA256SUMS.txt').write_text(''.join(f'{h}  {n}\n' for n, h in report['sha256'].items()), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'changes'}, indent=2))


if __name__ == '__main__':
    main()
