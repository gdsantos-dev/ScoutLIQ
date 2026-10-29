"""Verify extracted v1.38.6 sources and their embedded receipts, without mutation."""
import argparse
import hashlib
import json
from pathlib import Path
from apply_release_patch import safe

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    root = parser.parse_args().root.resolve(strict=True)
    manifest = json.loads((root/'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
    for name, expected in manifest.items():
        assert digest(safe(root, name).read_bytes()) == expected, 'Changed or missing source: '+name
    receipt = json.loads((root/'release/PACKAGE-VALIDATION.json').read_text(encoding='utf-8'))
    payload = {name: value for name, value in manifest.items() if name not in (
        'release/PACKAGE-VALIDATION.json', 'release/SHA256SUMS.txt')}
    assert receipt['version'] == '1.38.6-dev'
    assert digest(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()) == receipt['payload_manifest_sha256']
    checks = {}
    for line in (root/'release/SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'): continue
        value, name = line.split('  ', 1)
        checks[name] = value
    assert checks == payload, 'Source checksum receipt does not match manifest'
    print(json.dumps({'version': receipt['version'], 'verified_files': len(manifest), 'embedded_receipts': True}))

if __name__ == '__main__': main()
