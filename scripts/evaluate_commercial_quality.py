"""Reproducible controlled selection evidence; not human labels or real commercial outcomes."""
import json
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.scoring import score
from backend.selection_quality import metrics, reviewed_metrics


def evaluate():
    fixtures=json.loads((ROOT/'tests/fixtures/commercial-evaluation-v132.json').read_text(encoding='utf-8'))
    rows=[]
    for fixture in fixtures:
        current=score(SimpleNamespace(**fixture['input']))
        rows.append({'id':fixture['id'],'expected':fixture['expected_controlled_label']=='qualified',
                     'selected':current['status']=='qualified','score':current['value'],
                     'baseline_selected':fixture['after']['status']=='qualified','baseline_score':fixture['after']['value']})
    baseline=[{**r,'selected':r['baseline_selected'],'score':r['baseline_score']} for r in rows]
    return {'fixture_origin':'synthetic controlled acceptance, inherited independently of v1.34 implementation',
        'score_version':'3.0','baseline_v133':metrics(baseline),'candidate_v134':metrics(rows),
        'rows':rows,'human_reviewed_cases':0,'commercial_outcomes':0,
        'real_commercial_quality':None,
        'limitations':['No measured improvement in real opportunity quality or conversion.',
                      'No external model/provider calls; semantic correctness requires representative reviewed cases.',
                      'Adaptive allocation is a bounded heuristic, not a learned ranking model.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Avaliação controlada ou de casos explicitamente exportados pelo operador; sem alterar o Score.')
    parser.add_argument('--reviewed-export',type=Path)
    parser.add_argument('--dataset')
    parser.add_argument('--split',choices=('development','validation'))
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/commercial-quality.json')
    args=parser.parse_args()
    if args.reviewed_export:
        if not args.dataset or not args.split: parser.error('Informe --dataset e --split para separar as amostras.')
        if args.reviewed_export.stat().st_size>20*1024*1024: parser.error('Exportação excede 20 MB; use um recorte do conjunto.')
        try:
            source=json.loads(args.reviewed_export.read_text(encoding='utf-8'))
            cases=source['commercial_learning']['cases']
            if not isinstance(cases,list) or len(cases)>2000: raise ValueError()
            cases=sorted([c for c in cases if c['record']['dataset']==args.dataset and c['record']['split']==args.split],key=lambda c:c['id'])
            if not cases: raise ValueError()
            report=reviewed_metrics(cases)
        except (ValueError,KeyError,TypeError): parser.error('Exportação inválida ou conjunto sem casos.')
        result={'source':'explicit_operator_export','dataset':args.dataset,'split':args.split,
                'human_reviews_declared_not_independently_verified':True,'report':report}
    else:
        result=evaluate()
    target=args.output;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(target)
