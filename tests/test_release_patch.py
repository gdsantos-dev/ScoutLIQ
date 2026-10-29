"""Release updater safety: exercise conflicts, tampering and interrupted writes."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/apply_release_patch.py'


def digest(value):
    return hashlib.sha256(value).hexdigest() if value is not None else None


@pytest.fixture
def patch_case(tmp_path, monkeypatch):
    target, package = tmp_path / 'target', tmp_path / 'patch'
    target.mkdir()
    package.mkdir()
    before = {
        'frontend/package.json': b'{"version":"1.19.1"}',
        'backend/main.py': b'# unchanged backend',
        'old.ts': b'old implementation',
        'removed.ts': b'obsolete source',
        '.env': b'LOCAL_ONLY=synthetic-sentinel',
        'data/app.db': b'synthetic-database-sentinel',
    }
    after = {
        'frontend/package.json': b'{"version":"1.20.0"}',
        'old.ts': b'new implementation',
        'removed.ts': None,
        'new.ts': b'new file',
    }
    for name, data in before.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    changes = []
    for name, data in after.items():
        changes.append({'path': name, 'before_sha256': digest(before.get(name)), 'after_sha256': digest(data)})
        if data is not None:
            path = package / 'files' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    manifest = {'from': '1.19.1', 'to': '1.20.0', 'changes': changes}
    (package / 'PATCH-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('release_patch_test', SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, '__file__', str(package / 'apply_release_patch.py'))
    monkeypatch.setattr(sys, 'argv', ['apply_release_patch.py', '--target', str(target)])
    return module, target, package, before, after


def assert_original(target, before):
    for name, data in before.items():
        assert (target / name).read_bytes() == data
    assert not (target / 'new.ts').exists()


def test_dry_run_never_writes(patch_case):
    module, target, _, before, _ = patch_case
    module.main()
    assert_original(target, before)
    assert not (target / '.scoutliq-backups').exists()


def test_apply_preserves_runtime_and_backs_up_sources(patch_case, monkeypatch):
    module, target, _, before, after = patch_case
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--apply'])
    module.main()
    for name, data in after.items():
        if data is None:
            assert not (target / name).exists()
        else:
            assert (target / name).read_bytes() == data
    for name in ['backend/main.py', '.env', 'data/app.db']:
        assert (target / name).read_bytes() == before[name]
    backup, = (target / '.scoutliq-backups').iterdir()
    for name in ['frontend/package.json', 'old.ts', 'removed.ts']:
        assert (backup / name).read_bytes() == before[name]
    with pytest.raises(ValueError, match='Expected 1.19.1'):
        module.main()


def test_conflict_rejects_entire_patch(patch_case, monkeypatch):
    module, target, _, before, _ = patch_case
    before['old.ts'] = b'local custom change'
    (target / 'old.ts').write_bytes(before['old.ts'])
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--apply'])
    with pytest.raises(ValueError, match='nothing changed'):
        module.main()
    assert_original(target, before)
    assert not (target / '.scoutliq-backups').exists()


def test_tampered_payload_rejects_entire_patch(patch_case, monkeypatch):
    module, target, package, before, _ = patch_case
    (package / 'files/new.ts').write_bytes(b'corrupted payload')
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--apply'])
    with pytest.raises(ValueError, match='Damaged patch payload'):
        module.main()
    assert_original(target, before)
    assert not (target / '.scoutliq-backups').exists()


def test_interrupted_copy_rolls_back_updates_and_deletions(patch_case, monkeypatch):
    module, target, _, before, _ = patch_case
    copy = module.atomic_copy

    def interrupted(source, destination):
        if destination.name == 'new.ts':
            raise OSError('simulated failed write')
        copy(source, destination)

    monkeypatch.setattr(module, 'atomic_copy', interrupted)
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--apply'])
    with pytest.raises(OSError, match='simulated failed write'):
        module.main()
    assert_original(target, before)


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'C:/outside', 'folder\\outside', '.'])
def test_unsafe_paths_rejected(patch_case, name):
    module, target, *_ = patch_case
    with pytest.raises(ValueError):
        module.safe(target, name)
