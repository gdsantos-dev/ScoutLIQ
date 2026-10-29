"""Saved-query predicates equivalent to Radar filters, applied to server results."""
def matches(row, query):
    score = row['score']
    diagnoses = score.get('diagnosis', [])
    keys = {d['key'] for d in diagnoses}
    problems = {
        'no_site': row['website_status'] == 'none' or bool(keys & {'no_website', 'aggregator_website'}),
        'website_issues': row['website_status'] == 'poor' or any(d['area'] in ('mobile','performance','technical','conversion','accessibility','discoverability') for d in diagnoses),
        'booking_gap': 'niche_booking' in keys,
        'menu_gap': 'niche_catalog_or_menu' in keys and score['niche']['key'] == 'food',
        'catalog_gap': 'niche_catalog_or_menu' in keys and score['niche']['key'] != 'food',
        'ecommerce_gap': 'niche_ecommerce' in keys,
        'weak_digital': row['website_status'] in ('none','poor') or score['dimensions']['digital_need']['value'] >= 28,
        'competitive_gap': bool((score.get('competitive') or {}).get('site_gap')),
    }
    if not all(problems.get(k, False) for k in query.get('problem_keys', [])): return False
    for key, value in [('min_score', score['value']), ('min_rating', row.get('rating') or 0),
                       ('min_reviews', row.get('reviews') or 0), ('min_confidence', score['confidence']['value']),
                       ('min_timing', score['timing']['value'])]:
        if query.get(key, 0) > value: return False
    contact = query.get('contact_filter')
    if contact == 'any' and not any(row.get(k) for k in ('phone','whatsapp','instagram')): return False
    if contact in ('phone','whatsapp','instagram') and not row.get(contact): return False
    if query.get('service_key'):
        fit = next((s for s in score['service_scores'] if s['key'] == query['service_key']), None)
        if not fit or fit['value'] < (query.get('min_service_score') or 60): return False
    return True
