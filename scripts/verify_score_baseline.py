"""Compare default Score 3.0 against the exact authorized v1.36 FULL, not self-derived expectations."""
import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
BASE_SHA='64f09d40b18c1e6048b94bb3f87394c9a0bf74e455d37a20ccfbd35eb02a0e75'


def verify(base):
    if hashlib.sha256(base.read_bytes()).hexdigest()!=BASE_SHA: raise ValueError('Exact v1.36 FULL required')
    from backend.scoring import score
    cases=json.loads((ROOT/'tests/fixtures/commercial-evaluation-v132.json').read_text(encoding='utf-8'))
    inputs=[]
    for case in cases:
        original=case['input'];inputs.append(original)
        for field,values in {'website_status':['unknown','none','poor','good'], 'reviews':[0,1,30,100,1000],
            'rating':[0,2.5,4,4.8,5], 'instagram_active':[False,True], 'contact_blocked':[False,True],
            'stage':['discovered','qualified','won','lost'], 'demo':[False,True]}.items():
            inputs.extend({**original,field:value} for value in values)
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='score-baseline-',dir=artifacts) as directory:
        path=Path(directory)/'scoring_v136.py'
        with ZipFile(base) as archive:path.write_bytes(archive.read('ScoutLIQ/backend/scoring.py'))
        spec=importlib.util.spec_from_file_location('backend._scoutliq_authorized_v136_scoring',path)
        baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
        for index,data in enumerate(inputs):
            assert score(SimpleNamespace(**data))==baseline.score(SimpleNamespace(**data)),f'Default Score differs for controlled case {index}'
    result={'base_sha256':BASE_SHA,'default_score_complete_results_equal':True,'controlled_cases':len(inputs),
        'commercial_quality_claim':False}
    (artifacts/'score-baseline-v137.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True)
    print(json.dumps(verify(parser.parse_args().base),indent=2))
