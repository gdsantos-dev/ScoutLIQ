"""Evaluation only: never modifies Score Engine weights or production labels."""
from math import log2
from collections import Counter


def metrics(rows, k=10):
    """Rows contain an independent expected label, selection and existing Score 3.0 value."""
    labeled = [r for r in rows if type(r.get('expected')) is bool]
    tp = sum(r['expected'] and r['selected'] for r in labeled)
    fp = sum(not r['expected'] and r['selected'] for r in labeled)
    fn = sum(r['expected'] and not r['selected'] for r in labeled)
    tn = sum(not r['expected'] and not r['selected'] for r in labeled)
    ranked = sorted(labeled, key=lambda r:r['score'], reverse=True)[:k]
    ideal = sorted(labeled, key=lambda r:r['expected'], reverse=True)[:k]
    def dcg(items): return sum(int(r['expected']) / log2(i+2) for i,r in enumerate(items))
    return {'cases':len(rows), 'labeled':len(labeled), 'tp':tp, 'fp':fp, 'fn':fn, 'tn':tn,
        'precision':tp/(tp+fp) if tp+fp else None, 'recall':tp/(tp+fn) if tp+fn else None,
        'precision_at_k':sum(r['expected'] for r in ranked)/len(ranked) if ranked else None,
        'ndcg_at_k':dcg(ranked)/dcg(ideal) if dcg(ideal) else None, 'k':k}


def reviewed_metrics(cases, k=10):
    """Descriptive agreement, with abstentions and outcomes kept out of the binary confusion matrix.

    Ranking uses all labeled cases with an observed numerical score, including abstentions.
    Imported scores are declarations and remain identifiable in cohorts and limitations.
    """
    def label(case):
        record = case['record']
        if record['review_status'] != 'reviewed': return None
        return {'suitable': True, 'unsuitable': False}.get(record['classification'])

    def summarize(items):
        labeled = [c for c in items if label(c) is not None]
        decided = [c for c in labeled if c['system']['decision'] in ('selected', 'rejected')]
        rows = [{'expected': label(c), 'selected': c['system']['decision'] == 'selected',
                 'score': c['system']['score']} for c in decided]
        result = metrics(rows, k)
        ranked = [c for c in labeled if type(c['system'].get('score')) in (int, float)]
        ranking = metrics([{'expected': label(c), 'selected': False, 'score': c['system']['score']} for c in ranked], k)
        result.update(cases=len(items), labeled=len(labeled), decided=len(decided), ranked=len(ranked),
            precision_at_k=ranking['precision_at_k'], ndcg_at_k=ranking['ndcg_at_k'], effective_k=min(k, len(ranked)),
            label_coverage=len(labeled)/len(items) if items else None,
            decision_coverage=len(decided)/len(labeled) if labeled else None,
            abstention_rate=(len(labeled)-len(decided))/len(labeled) if labeled else None,
            abstained_positive=sum(label(c) is True and c['system']['decision'] == 'abstained' for c in labeled),
            disagreement=(result['fp']+result['fn'])/len(decided) if decided else None,
            sufficient_sample=len(decided) >= 30 and result['tp']+result['fp'] >= 10 and result['tp']+result['fn'] >= 10)
        # Wilson 95% interval for precision; descriptive only, no independence claim.
        n, hits = result['tp']+result['fp'], result['tp']
        if n:
            p, z = hits/n, 1.96
            center = (p+z*z/(2*n))/(1+z*z/n)
            width = z*((p*(1-p)/n+z*z/(4*n*n))**.5)/(1+z*z/n)
            result['precision_interval_95'] = [max(0, center-width), min(1, center+width)]
        else: result['precision_interval_95'] = None
        return result

    def groups(key):
        values = {}
        for c in cases: values.setdefault(key(c), []).append(c)
        return [{'group': name, **summarize(items)} for name, items in sorted(values.items())]

    comparison = []
    for case in cases:
        expected, system = label(case), case['system']
        agreement = ('unlabeled' if expected is None else 'abstained' if system['decision'] == 'abstained'
                     else 'tp' if expected and system['decision'] == 'selected'
                     else 'fn' if expected else 'fp' if system['decision'] == 'selected' else 'tn')
        comparison.append({'case_id': case['id'], 'case_version': case['version'], 'agreement': agreement,
                           'human': case['record']['classification'], 'system': system['decision'],
                           'criteria_version': system.get('criteria_version')})
    return {'metrics': summarize(cases), 'by_sector': groups(lambda c: c['record']['company']['sector']),
        'by_region': groups(lambda c: c['record']['company']['country'] + '/' + (c['record']['company']['region'] or c['record']['company']['city'])),
        'by_criteria': groups(lambda c: c['system']['origin'] + ':' + str(c['system'].get('criteria_version'))),
        'outcomes': dict(Counter(c['record']['outcome'] for c in cases)), 'comparison': comparison,
        'limitations': ['Revisões humanas declaradas pelo operador; a importação não comprova a origem.',
            'A decisão registrada é a qualificação do Score 3.0; não inclui filtros particulares de uma busca.',
            'Amostra de conveniência, sem garantia de representatividade ou independência estatística.',
            'Contagens são descritivas. O indicador de amostra exige 30 decisões, 10 seleções e 10 positivos humanos; não comprova generalização.',
            'Abstenções não são rejeições: ficam fora da matriz binária. Positivos abstidos aparecem separadamente.',
            'Ordenação inclui todos os casos rotulados com score registrado; empates seguem a ordem estável dos IDs.',
            'Versões e scores externos não são necessariamente comparáveis: examine os grupos por critério.',
            'Resultados comerciais não alteram rótulos, critérios ou pesos. Não há inferência causal de conversão.']}
