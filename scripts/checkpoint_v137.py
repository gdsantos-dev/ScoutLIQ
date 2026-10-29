"""Freeze/verify v1.37 sources, exact baseline and explicitly reviewed engine adaptations."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from build_release import ROOT, digest, source_files

AUTHORIZED_BASE = '64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75'
PROTECTED = (
    'backend/scoring.py', 'backend/commercial_fit.py',
    'backend/outreach_intelligence.py',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if digest(args.base.read_bytes()) != AUTHORIZED_BASE:
        raise ValueError('Exact authorized v1.36 FULL required')
    with ZipFile(args.base) as archive:
        manifest = json.loads(archive.read('ScoutLIQ/RELEASE-MANIFEST.json'))
        for name, expected in manifest.items():
            if digest(archive.read('ScoutLIQ/' + name)) != expected:
                raise ValueError('Baseline manifest mismatch: ' + name)
    current = {name: digest(data) for name, data in source_files().items()}
    reviewed=json.loads((ROOT/'docs/REVIEWED-ENGINE-CHANGES-v1.37.json').read_text(encoding='utf-8'))
    for name, expected in reviewed.items():
        if current.get(name)!=expected: raise ValueError('Reviewed adaptation changed: '+name)
    for name in PROTECTED:
        if current.get(name) != manifest.get(name):
            raise ValueError('Protected engine changed: ' + name)
    for name in manifest:
        if name.startswith(('backend/','migrations/')) and name not in reviewed and current.get(name) != manifest[name]:
            raise ValueError('Unreviewed engine or migration change: ' + name)
    destination = ROOT / 'artifacts/v137-checkpoint.json'
    if args.verify:
        recorded = json.loads(destination.read_text(encoding='utf-8'))
        if recorded['sources'] != current:
            raise ValueError('Sources differ from recorded checkpoint')
        print(f'Checkpoint verified: {len(current)} sources; protected engines unchanged; reviewed adaptations match hashes.')
        return
    changes = [{
        'path': name, 'before_sha256': manifest.get(name), 'after_sha256': current.get(name)
    } for name in sorted(set(manifest) | set(current)) if manifest.get(name) != current.get(name)]
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps({
        'status': 'source_checkpoint_see_validation_report',
        'base_archive_sha256': AUTHORIZED_BASE,
        'sources': current,
        'changes': changes,
        'protected_engines': list(PROTECTED),
        'migration_status': '027_additive_cache_historical_revisions_unchanged',
        'reviewed_adaptations': reviewed,
    }, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Checkpoint recorded: {len(current)} sources, {len(changes)} differences from v1.36.')


if __name__ == '__main__':
    main()
