"""Independently check ZIPs and exercise a source-only, disposable installation."""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
import tempfile
from zipfile import ZipFile

root=Path(__file__).resolve().parents[1]
release=root/'release';full=release/'ScoutLIQ-v1.38.6-dev-FULL.zip'
report=json.loads((release/'PACKAGE-VALIDATION.json').read_text(encoding='utf-8'))
for name,expected in report['sha256'].items():
    archive=release/name
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
    with ZipFile(archive) as z:
        assert z.testzip() is None
        for name in z.namelist():
            path=PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
            assert not set(path.parts)&{'.git','.venv','node_modules','data','dist','artifacts'}
            assert path.suffix not in {'.db','.sqlite','.sqlite3','.key','.pem','.pyc'}
            assert not path.name.startswith('.env') or path.name=='.env.example'
fresh=Path(tempfile.mkdtemp(prefix='clean-full-',dir=root/'artifacts')).resolve()
with ZipFile(full) as z:
    for item in z.infolist():
        if item.is_dir():continue
        path=(fresh/item.filename).resolve();assert path.is_relative_to(fresh)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(item))
app=fresh/'ScoutLIQ'
assert not (app/'artifacts').exists() and not (app/'frontend/dist').exists() and not (app/'frontend/node_modules').exists()
env={**os.environ,'TEMP':str(root/'artifacts/tmp'),'TMP':str(root/'artifacts/tmp')}
result=subprocess.run([sys.executable,'-m','pytest','tests/test_operational_intelligence.py','tests/test_commercial_volume.py','-q','--basetemp',str(fresh/'pytest-temp')],
    cwd=app,env=env,capture_output=True,text=True,timeout=300)
(release/'CLEAN-INSTALL-TEST.txt').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
assert result.returncode==0,result.stdout+result.stderr
assert '38 passed' in result.stdout
assert (app/'artifacts/commercial-volume.json').is_file()
manifest=json.loads((app/'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((app/name).read_bytes()).hexdigest()==h for name,h in manifest.items())
assert all((root/name).read_bytes()==(app/name).read_bytes() for name in manifest if not name.startswith('release/'))
receipt={'version':'1.38.6-dev','full_sha256':hashlib.sha256(full.read_bytes()).hexdigest(),
    'clean_extract':True,'no_artifacts_preparation':True,'no_frontend_dist_or_dependencies':True,
    'tests_passed':38,'volume_test_passed':True,'output_created_by_test':True,'source_manifest_unchanged_after_test':True,
    'packaged_source_matches_candidate':True,'archive_crc_and_hashes_verified':True,'runtime_exclusions_verified':True,
    'scope':'Local isolated SQLite; no production, external providers or sends.'}
(release/'CLEAN-INSTALL-VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
