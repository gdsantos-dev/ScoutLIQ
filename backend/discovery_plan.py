"""Finite adaptive allocation over the configured provider, not an AI-created source list."""


def initialize(coverage):
    return {'version': '1', 'steps': [dict(sector=c['sector'], offset=0, pages=0,
        exhausted=not c['supported'], candidate_ids=[], qualified=0, discarded=0)
        for c in coverage], 'decision': 'Cobrir primeiro os setores suportados pela fonte configurada.'}


def record(info, result, ids):
    plan = info.get('plan')
    if not plan: return  # Resume an old v1.33 job with its original cursor.
    step = plan['steps'][info['sector']]
    scanned = max(result.scanned, len(result.results))
    step['offset'] += scanned; step['pages'] += 1
    new = set(ids) - set(step['candidate_ids'])
    step['candidate_ids'] = list(dict.fromkeys([*step['candidate_ids'], *ids]))
    step['stalled'] = step.get('stalled', 0) + 1 if not new else 0
    step['exhausted'] = result.complete or not scanned or not info['coverage'][info['sector']]['pagination'] or step['stalled'] >= 2


def choose(info):
    plan = info.get('plan')
    if not plan: return
    entries = {e['id']: e for e in info['candidates']}
    for step in plan['steps']:
        rows = [entries[i] for i in step['candidate_ids'] if i in entries]
        for key in ('qualified', 'discarded'):
            step[key] = sum(e['group'] == key for e in rows)
    available = [(i, s) for i, s in enumerate(plan['steps']) if not s['exhausted']]
    if not available:
        info['sector'] = len(plan['steps']); info['offset'] = 0
        plan['decision'] = 'Cobertura disponível esgotada; resultados parciais preservados.'
        return
    # Every supported sector gets its first page. Afterwards observed yield per page
    # allocates discovery, with an exploration term to avoid starving sparse sectors.
    def utility(item):
        index, step = item
        if not step['pages']: return (1, 0, -index)
        yield_per_page = step['qualified'] / step['pages']
        exploration = 1 / (step['pages'] + 1)
        return (0, yield_per_page + exploration, -index)
    index, step = max(available, key=utility)
    info['sector'], info['offset'] = index, step['offset']
    plan['decision'] = ('Primeira página do setor ' if not step['pages'] else 'Próxima página por rendimento observado e cobertura: ') + (step['sector'] or 'Exploração geral') + '.'


def describe(info):
    plan = info.get('plan')
    if not plan: return None
    return {'version': plan['version'], 'decision': plan['decision'],
        'steps': [{k: s[k] for k in ('sector', 'offset', 'pages', 'exhausted', 'qualified', 'discarded')} for s in plan['steps']],
        'scope': 'Alocação de coleta por resultados técnicos observados; não mede conversão comercial.'}


def diverse(rows, quality, category, previous=()):
    """Interleave observed categories only within equal quality strata.

    Does not change scores or bring discarded companies into the candidate set.
    Research uses ten-point bands; final qualification uses exact score/tie keys.
    """
    from collections import Counter
    counts=Counter(previous)
    groups={}
    for row in rows: groups.setdefault(quality(row),[]).append(row)
    result=[]
    for key in sorted(groups,reverse=True):
        pending=groups[key][:]
        while pending:
            index=min(range(len(pending)),key=lambda i:(counts[category(pending[i])],i))
            row=pending.pop(index);result.append(row);counts[category(row)]+=1
    return result
