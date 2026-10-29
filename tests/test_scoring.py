import json
from types import SimpleNamespace

from backend.scoring import score


def lead(**overrides):
    base = dict(
        name="Empresa Teste",
        category="Serviços",
        website="https://example.com",
        website_status="good",
        source="manual",
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "social": True,
            "whatsapp_site": True,
        }),
        reviews=0,
        rating=0,
        whatsapp="",
        phone="",
        instagram="",
        instagram_active=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_niche_context_changes_relevant_capability_score():
    clinic = lead(
        name="Clínica Sorriso",
        category="Clínica odontológica",
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "social": True,
            "whatsapp_site": True,
            "booking": False,
        }),
    )
    result = score(clinic)
    assert result["niche"]["key"] == "healthcare"
    booking = next(item for item in result["niche"]["expectations"] if item["key"] == "booking")
    assert booking["state"] == "missing"
    assert any(item["key"] == "niche_booking" and item["points"] == 8 for item in result["reasons"])
    assert any(item["key"] == "niche_booking" and item["severity"] == "high" for item in result["diagnosis"])


def test_niche_gap_is_not_invented_without_audit():
    clinic = lead(
        category="Clínica médica",
        website_intelligence_json=json.dumps({"pages_checked": 0, "booking": False}),
    )
    result = score(clinic)
    assert result["niche"]["key"] == "healthcare"
    assert all(item["state"] == "unknown" for item in result["niche"]["expectations"])
    assert not any(item["key"].startswith("niche_") for item in result["reasons"])
    assert not any(item["key"].startswith("niche_") for item in result["diagnosis"])


def test_structured_diagnosis_uses_verified_audit_findings():
    audited = lead(
        category="Consultoria empresarial",
        website_status="poor",
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "quality_score": 52,
            "high_findings": 1,
            "medium_findings": 1,
            "own_domain": True,
            "forms": 1,
            "findings": [
                {"key": "no_cta", "severity": "high", "detail": ""},
                {"key": "slow_response", "severity": "medium", "detail": "Até 5100 ms"},
            ],
        }),
    )
    result = score(audited)
    keys = {item["key"] for item in result["diagnosis"]}
    assert "no_cta" in keys
    assert "slow_response" in keys
    assert result["diagnosis"][0]["severity"] == "high"


def test_service_fit_prefers_site_for_confirmed_no_website():
    candidate = lead(
        category="Consultoria empresarial",
        website="",
        website_status="none",
        reviews=180,
        rating=4.7,
        phone="+5581999999999",
        website_intelligence_json=json.dumps({"pages_checked": 0}),
    )
    result = score(candidate)
    services = result["service_scores"]
    assert services
    assert services[0]["key"] == "site_institucional"
    assert services[0]["value"] >= 80
    assert not any(item["key"] == "redesign" and item["value"] >= services[0]["value"] for item in services)


def test_service_fit_uses_verified_niche_gap_for_booking():
    clinic = lead(
        category="Clínica odontológica",
        reviews=220,
        rating=4.8,
        phone="+5581999999999",
        whatsapp="+5581999999999",
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "social": True,
            "whatsapp_site": True,
            "booking": False,
        }),
    )
    result = score(clinic)
    booking = next(item for item in result["service_scores"] if item["key"] == "sistema_agendamento")
    assert booking["value"] >= 70
    assert "Agendamento relevante para este nicho" in booking["signals"]


def test_confidence_rewards_verified_coverage_without_changing_opportunity_meaning():
    sparse = lead(
        category="",
        website="",
        website_status="unknown",
        website_intelligence_json="",
        reviews=0,
        rating=0,
        phone="",
        whatsapp="",
        instagram="",
    )
    rich = lead(
        name="Clínica Sorriso",
        category="Clínica odontológica",
        city="Recife",
        address="Av. Exemplo, 100",
        website="https://clinicasorriso.com.br",
        website_status="good",
        reviews=320,
        rating=4.8,
        phone="+558132323232",
        whatsapp="+5581999999999",
        instagram="@clinicasorriso",
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "email": True,
            "social": True,
            "whatsapp_site": True,
            "booking": True,
        }),
    )
    sparse_result = score(sparse)
    rich_result = score(rich)
    assert sparse_result["confidence"]["value"] < 55
    assert sparse_result["confidence"]["level"] == "low"
    assert rich_result["confidence"]["value"] >= 80
    assert rich_result["confidence"]["level"] == "high"
    assert rich_result["confidence"]["value"] != rich_result["value"]


def test_confirmed_no_website_counts_as_verified_website_evidence():
    candidate = lead(
        category="Serviços profissionais",
        website="",
        website_status="none",
        reviews=40,
        rating=4.5,
        phone="+558132323232",
        website_intelligence_json=json.dumps({"pages_checked": 0}),
    )
    result = score(candidate)
    assert result["confidence"]["components"]["website_verification"]["value"] == 25
    assert "Verificação do site" not in result["confidence"]["missing"]


def test_competitive_context_strengthens_verified_local_gap():
    candidate = lead(
        category="Clínica odontológica",
        website_status="poor",
        reviews=260,
        rating=4.8,
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "social": True,
            "whatsapp_site": True,
            "booking": True,
            "quality_score": 62,
        }),
    )
    candidate.competitive_context_json = json.dumps({
        "status": "ready",
        "radius_km": 5,
        "peers_count": 8,
        "known_site_peers": 7,
        "peer_site_rate": 100,
        "strong_site_rate": 71,
        "median_reviews": 140,
        "median_rating": 4.6,
        "review_percentile": 75,
        "target_site_state": "weak",
        "site_gap": "weak",
        "demand_above_median": True,
        "sample_quality": "high",
        "niche_key": "healthcare",
    })
    result = score(candidate)
    keys = {item["key"] for item in result["reasons"]}
    assert "competitive_site_gap" in keys
    assert result["competitive"]["peers_count"] == 8
    assert result["competitive"]["site_gap"] == "weak"


def test_competitive_context_never_scores_an_insufficient_sample():
    candidate = lead(website_status="poor")
    candidate.competitive_context_json = json.dumps({
        "status": "insufficient",
        "peers_count": 2,
        "known_site_peers": 2,
        "site_gap": "weak",
        "demand_above_median": True,
    })
    result = score(candidate)
    assert not any(item["key"].startswith("competitive_") for item in result["reasons"])


def test_commercial_structure_uses_observable_operating_signals_not_financial_claims():
    candidate = lead(
        category="Clínica odontológica",
        reviews=820,
        rating=4.8,
        phone="+558132323232",
        whatsapp="+5581999999999",
        instagram="@clinica",
        instagram_active=True,
        website_intelligence_json=json.dumps({
            "pages_checked": 3,
            "own_domain": True,
            "forms": 1,
            "email": True,
            "social": True,
            "analytics": ["ga4", "gtm"],
            "booking": True,
            "live_chat": True,
        }),
        commercial_signal_json=json.dumps({"brand_locations": 2, "events": []}),
    )
    result = score(candidate)
    structure = result["commercial_structure"]
    assert structure["value"] >= 70
    assert structure["level"] == "high"
    assert structure["confidence"] >= 80
    assert any(item["key"] == "multiple_locations" for item in structure["signals"])
    assert any(item["key"] == "reviews" for item in structure["signals"])


def test_timing_uses_recent_change_and_local_pressure_without_changing_opportunity_score():
    import time

    candidate = lead(
        category="Clínica odontológica",
        website="",
        website_status="none",
        reviews=340,
        rating=4.8,
        phone="+558132323232",
        whatsapp="+5581999999999",
        commercial_signal_json=json.dumps({
            "brand_locations": 1,
            "events": [
                {"key": "reviews_growth_strong", "at": int(time.time()), "detail": "+40 avaliações desde a observação anterior"}
            ],
        }),
    )
    candidate.competitive_context_json = json.dumps({
        "status": "ready",
        "radius_km": 5,
        "peers_count": 8,
        "known_site_peers": 7,
        "peer_site_rate": 86,
        "strong_site_rate": 71,
        "median_reviews": 140,
        "median_rating": 4.6,
        "review_percentile": 88,
        "target_site_state": "missing",
        "site_gap": "missing",
        "demand_above_median": True,
        "sample_quality": "high",
        "niche_key": "healthcare",
    })
    candidate.competitive_analyzed_at = int(time.time())
    result = score(candidate)
    assert result["timing"]["level"] == "high"
    assert result["timing"]["value"] >= 55
    keys = {item["key"] for item in result["timing"]["signals"]}
    assert "reviews_growth_strong" in keys
    assert "local_pressure" in keys
    assert result["value"] <= 100


def test_new_website_can_reduce_timing_instead_of_being_treated_as_positive():
    import time

    candidate = lead(
        website="https://example.com",
        website_status="good",
        reviews=12,
        commercial_signal_json=json.dumps({
            "brand_locations": 1,
            "events": [{"key": "website_new", "at": int(time.time()), "detail": "Um site passou a ser confirmado"}],
        }),
    )
    result = score(candidate)
    assert result["timing"]["value"] == 0
    assert result["timing"]["level"] == "low"
    assert any(item["effect"] == "negative" for item in result["timing"]["signals"])
