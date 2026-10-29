"""Derive the verified packaging workflow from the immediate FULL base."""
import hashlib,json
from pathlib import Path
from zipfile import ZipFile
root=Path(__file__).resolve().parents[1]
base=root.parent.parent/'v1.38.6-dev/ScoutLIQ/release/ScoutLIQ-v1.38.6-dev-FULL.zip'
sha='dbf392f49ae3c13e699b7b345743f164774953717747f39c06b136e1e1a04f79'
assert hashlib.sha256(base.read_bytes()).hexdigest()==sha
def advance(text):
    return text.replace('1.38.6','1.38.7').replace('1.38.5','1.38.6').replace('7310028178df19e949295990cd81bba4037f5c04dd94f1602d463564fb8bfb22',sha)
pack=advance((root/'scripts/package_operations_v1386.py').read_text(encoding='utf-8'))
pack=pack.replace("('operations-desktop.png','operations-efficiency-desktop.png','operations-390.png','operations-320.png')","('planning-desktop.png','planning-progress-desktop.png','planning-390.png','planning-320.png')")
pack=pack.replace('verify_operations_package.py','verify_planning_package.py')
(root/'scripts/package_planning_v1387.py').write_text(pack,encoding='utf-8')
verify=advance((root/'scripts/verify_operations_package.py').read_text(encoding='utf-8'))
(root/'scripts/verify_planning_package.py').write_text(verify,encoding='utf-8')
clean=advance((root/'scripts/verify_operations_clean_install.py').read_text(encoding='utf-8'))
clean=clean.replace("'tests/test_operational_intelligence.py','tests/test_commercial_volume.py'","'tests/test_operational_intelligence.py','tests/test_commercial_volume.py','tests/test_prospecting.py','tests/test_prospecting_migration.py'")
clean=clean.replace("'38 passed'","'79 passed'").replace("'tests_passed':38","'tests_passed':79")
(root/'scripts/verify_planning_clean_install.py').write_text(clean,encoding='utf-8')
with ZipFile(base) as z:
    baseline={n.removeprefix('ScoutLIQ/'):z.read(n) for n in z.namelist() if not n.endswith('/')}
    previous=json.loads(baseline['docs/qa-v1.38.6-dev/preserved-engines.json'])['sha256']
allowed={'backend/consumption.py','backend/routines.py','backend/smart_search.py'}
proof={}
for name in previous:
    if name in allowed:continue
    assert (root/name).read_bytes()==baseline[name],name
    proof[name]=hashlib.sha256(baseline[name]).hexdigest()
for name in ('backend/operational_intelligence.py','backend/research_worker.py','backend/selection_quality.py'):
    assert (root/name).read_bytes()==baseline[name],name
    proof[name]=hashlib.sha256(baseline[name]).hexdigest()
(root/'artifacts/preserved-engines.json').write_text(json.dumps({'count':len(proof),'all_match_base':True,'sha256':proof},indent=2),encoding='utf-8')
(root/'DEV-OVERLAY-MANIFEST.json').write_text(json.dumps(dict(version='1.38.7-dev',base='1.38.6-dev',base_sha256=sha,
    migration='033',new_migration='033',preserved_files={n:True for n in proof},
    edited_engine_hooks=sorted(allowed),production_ready=False,real_sends=0,real_provider_calls=0),indent=2),encoding='utf-8')
print(json.dumps({'preserved':len(proof),'packaging_scripts':'prepared'}))
