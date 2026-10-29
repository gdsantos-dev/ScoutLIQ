from backend.radar_query import interpret_natural_radar_query


def test_natural_radar_query_extracts_location_problem_reviews_and_contact():
    plan = interpret_natural_radar_query(
        'dentistas em Recife sem site com mais de 100 avaliações e com WhatsApp'
    )
    query = plan['query']
    assert query['location'] == 'recife'
    assert query['category'] == 'dentistas'
    assert query['problem_keys'] == ['no_site']
    assert query['min_reviews'] == 100
    assert query['contact_filter'] == 'whatsapp'
    assert plan['unresolved'] == []


def test_natural_radar_query_supports_niche_gap_rating_and_radius():
    plan = interpret_natural_radar_query(
        'restaurantes em Boa Viagem sem cardápio nota 4,5+ raio de 5 km'
    )
    query = plan['query']
    assert query['location'] == 'boa viagem'
    assert query['category'] == 'restaurantes'
    assert query['problem_keys'] == ['menu_gap']
    assert query['min_rating'] == 4.5
    assert query['scope'] == 'radius'
    assert query['radius_km'] == 5


def test_natural_radar_query_uses_fallback_location_without_inventing_one():
    plan = interpret_natural_radar_query('empresas sem site', fallback_location='Recife, PE', fallback_country='BR')
    assert plan['query']['location'] == 'recife, pe'
    assert plan['query']['country'] == 'BR'
    assert plan['query']['category'] == ''
    assert plan['query']['problem_keys'] == ['no_site']
    assert plan['unresolved'] == []

    unresolved = interpret_natural_radar_query('empresas sem site')
    assert unresolved['query']['location'] == ''
    assert unresolved['unresolved'] == ['location']
