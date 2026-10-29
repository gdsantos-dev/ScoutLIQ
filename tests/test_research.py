from backend import main
from backend.research import ResearchError, _validate_public_url, candidate_domains
from backend.db import SessionLocal
from backend.models import LeadResearch
from sqlalchemy import select


def test_candidate_domains_strip_branch_suffix_for_brazil():
    urls = candidate_domains("Depaulo Car (Loja 2)", "BR")
    assert "https://depaulocar.com.br" in urls
    assert "https://www.depaulocar.com.br" in urls


def test_research_rejects_local_ssrf_targets():
    for url in ("http://127.0.0.1", "http://localhost", "http://[::1]"):
        try:
            _validate_public_url(url)
        except ResearchError:
            pass
        else:
            raise AssertionError(f"private target accepted: {url}")


class FakeResearcher:
    search_configured = True

    def research(self, lead, locale="pt-BR"):
        assert lead.name == "Empresa Teste"
        return {
            "status": "confirmed",
            "provider": "brave+direct",
            "website_url": "https://empresa.example/",
            "website_status": "poor",
            "confidence": 91,
            "checked_at": 1_700_000_000,
            "evidence": [
                {"key": "name_match", "value": "2/2"},
                {"key": "city_match", "value": "Recife"},
            ],
            "checks": [
                {"key": "https", "state": "pass"},
                {"key": "viewport", "state": "fail"},
            ],
            "sources": [
                {"url": "https://empresa.example/", "title": "Empresa Teste", "kind": "search"}
            ],
            "page": {"title": "Empresa Teste", "domain": "empresa.example", "elapsed_ms": 120},
            "contacts": {"phone": "", "whatsapp": "", "instagram": ""},
            "search_configured": True,
            "candidates_checked": 4,
            "fetch_errors": 1,
        }


def test_research_persists_evidence_and_updates_confirmed_website(auth, lead_data, monkeypatch):
    created = auth.post("/api/leads", json=lead_data)
    assert created.status_code == 201, created.text
    lead = created.json()

    monkeypatch.setattr(main, "website_researcher", FakeResearcher())
    response = auth.post(f"/api/leads/{lead['id']}/research")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["lead"]["website"] == "https://empresa.example/"
    assert payload["lead"]["website_status"] == "poor"
    assert payload["research"]["confidence"] == 91
    assert payload["research"]["status"] == "confirmed"
    assert payload["research"]["evidence"][0]["key"] == "name_match"

    loaded = auth.get(f"/api/leads/{lead['id']}/research")
    assert loaded.status_code == 200
    assert loaded.json()["research"]["page"]["domain"] == "empresa.example"
    with SessionLocal() as db:
        assert db.scalar(select(LeadResearch).where(LeadResearch.lead_id == lead["id"])) is not None


def test_research_does_not_claim_no_site_when_unverified(auth, lead_data, monkeypatch):
    created = auth.post("/api/leads", json=lead_data).json()

    class UnverifiedResearcher:
        def research(self, lead, locale="pt-BR"):
            return {
                "status": "unverified",
                "provider": "direct",
                "website_url": "",
                "website_status": "unknown",
                "confidence": 41,
                "checked_at": 1_700_000_000,
                "evidence": [{"key": "name_partial", "value": "1/2"}],
                "checks": [],
                "sources": [],
                "contacts": {},
                "search_configured": False,
                "candidates_checked": 6,
                "fetch_errors": 0,
            }

    monkeypatch.setattr(main, "website_researcher", UnverifiedResearcher())
    response = auth.post(f"/api/leads/{created['id']}/research")
    assert response.status_code == 200
    payload = response.json()
    assert payload["lead"]["website"] == ""
    # Research cannot turn an absence of evidence into a fake certainty.
    assert payload["lead"]["website_status"] == "none"
    assert payload["research"]["status"] == "unverified"


def _audit_page(**overrides):
    from backend.research import PageSnapshot
    base = dict(
        requested_url="https://empresa.example/",
        final_url="https://empresa.example/",
        title="Empresa Teste",
        description="Descrição comercial suficientemente completa para o teste.",
        text="Empresa Teste Recife contato serviços",
        html_lang="pt-BR",
        has_viewport=True,
        has_canonical=True,
        has_schema=True,
        has_favicon=True,
        generator="",
        phone_links=["tel:+5581999999999"],
        email_links=["mailto:oi@empresa.example"],
        whatsapp_links=["https://wa.me/5581999999999"],
        instagram_links=["https://instagram.com/empresa"],
        social_links=["https://instagram.com/empresa"],
        links=[
            ("https://empresa.example/contato", "Contato"),
            ("https://wa.me/5581999999999", "WhatsApp"),
            ("https://empresa.example/orcamento", "Solicitar orçamento"),
        ],
        form_count=1,
        h1_count=1,
        image_count=5,
        image_alt_count=5,
        button_count=2,
        labeled_button_count=2,
        mixed_content_count=0,
        elapsed_ms=400,
        body_bytes=80_000,
        truncated=False,
    )
    base.update(overrides)
    return PageSnapshot(**base)


def test_deep_audit_scores_strong_site_as_good():
    from backend.research import _audit_site
    home = _audit_page()
    contact = _audit_page(
        requested_url="https://empresa.example/contato",
        final_url="https://empresa.example/contato",
        title="Contato | Empresa Teste",
    )
    audit = _audit_site([home, contact])
    assert audit["quality_score"] >= 82
    assert audit["website_status"] == "good"
    assert audit["pages_checked"] == 2


def test_deep_audit_flags_weak_site_as_poor():
    from backend.research import _audit_site
    page = _audit_page(
        final_url="http://empresa.example/",
        requested_url="http://empresa.example/",
        description="",
        html_lang="",
        has_viewport=False,
        has_canonical=False,
        has_schema=False,
        has_favicon=False,
        phone_links=[],
        email_links=[],
        whatsapp_links=[],
        instagram_links=[],
        social_links=[],
        links=[],
        form_count=0,
        h1_count=0,
        image_count=10,
        image_alt_count=1,
        button_count=4,
        labeled_button_count=0,
        mixed_content_count=0,
        elapsed_ms=5000,
    )
    audit = _audit_site([page])
    assert audit["quality_score"] < 65
    assert audit["website_status"] == "poor"
    keys = {item["key"] for item in audit["findings"]}
    assert "no_viewport" in keys
    assert "no_cta" in keys


def test_deep_audit_endpoint_persists_audit(auth, lead_data, monkeypatch):
    created = auth.post("/api/leads", json=lead_data).json()

    class FakeDeepResearcher(FakeResearcher):
        def deep_audit(self, lead, website_url):
            assert website_url == "https://empresa.example/"
            return {
                "level": "deep",
                "quality_score": 52,
                "website_status": "poor",
                "pages_checked": 3,
                "categories": {
                    "technical": {"score": 18, "max": 30},
                    "discoverability": {"score": 12, "max": 25},
                    "conversion": {"score": 14, "max": 30},
                    "accessibility": {"score": 8, "max": 15},
                },
                "findings": [{"key": "no_cta", "severity": "high", "label": "Nenhuma ação comercial clara detectada", "detail": ""}],
                "pages": [],
                "signals": {},
                "audited_at": 1_700_000_100,
                "fetch_errors": 0,
            }

    monkeypatch.setattr(main, "website_researcher", FakeDeepResearcher())
    response = auth.post(f"/api/leads/{created['id']}/research/deep")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["lead"]["website_status"] == "poor"
    assert payload["research"]["audit_level"] == "deep"
    assert payload["research"]["audit"]["quality_score"] == 52
    assert payload["research"]["audited_at"] == 1_700_000_100



def test_batch_research_runs_deep_analysis_and_updates_progress(auth, lead_data, monkeypatch):
    first = auth.post("/api/leads", json=lead_data).json()
    second_data = {**lead_data, "name": "Empresa Dois", "latitude": -8.06, "longitude": -34.91}
    second = auth.post("/api/leads", json=second_data).json()

    class BatchResearcher(FakeResearcher):
        def research(self, lead, locale="pt-BR"):
            result = super().research(type("LeadProxy", (), {**lead.__dict__, "name": "Empresa Teste"})(), locale)
            result["website_url"] = f"https://{lead.id[:8]}.example/"
            result["page"] = {"title": lead.name, "domain": f"{lead.id[:8]}.example", "elapsed_ms": 90}
            return result

        def deep_audit(self, lead, website_url):
            return {
                "level": "deep",
                "quality_score": 48,
                "website_status": "poor",
                "pages_checked": 2,
                "categories": {},
                "findings": [],
                "angles": [],
                "pages": [],
                "signals": {},
                "audited_at": 1_700_000_200,
                "fetch_errors": 0,
            }

    monkeypatch.setattr(main, "website_researcher", BatchResearcher())
    created = auth.post(
        "/api/research/batches",
        json={"lead_ids": [first["id"], second["id"]], "mode": "deep", "stale_days": 0},
    )
    assert created.status_code == 201, created.text
    batch = created.json()["batch"]
    assert batch["total"] == 2
    assert batch["processed"] == 0

    step_one = auth.post(f"/api/research/batches/{batch['id']}/step")
    assert step_one.status_code == 200, step_one.text
    assert step_one.json()["batch"]["processed"] == 1
    assert step_one.json()["lead"]["website_status"] == "poor"

    step_two = auth.post(f"/api/research/batches/{batch['id']}/step")
    assert step_two.status_code == 200, step_two.text
    final = step_two.json()["batch"]
    assert final["status"] == "completed"
    assert final["processed"] == 2
    assert final["done"] == 2


def test_batch_research_can_pause_and_resume(auth, lead_data, monkeypatch):
    lead = auth.post("/api/leads", json=lead_data).json()
    monkeypatch.setattr(main, "website_researcher", FakeResearcher())
    created = auth.post(
        "/api/research/batches",
        json={"lead_ids": [lead["id"]], "mode": "web", "stale_days": 0},
    ).json()["batch"]

    paused = auth.post(f"/api/research/batches/{created['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["batch"]["status"] == "paused"
    no_step = auth.post(f"/api/research/batches/{created['id']}/step")
    assert no_step.json()["batch"]["processed"] == 0
    resumed = auth.post(f"/api/research/batches/{created['id']}/resume")
    assert resumed.json()["batch"]["status"] == "pending"


def test_page_intelligence_detects_platform_analytics_and_commercial_features():
    from backend.research import _page_intelligence
    source = '''
    <html><head>
      <script src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>
      <link href="https://static.wixstatic.com/site.css" rel="stylesheet">
    </head><body>
      <a href="/agendar">Agendar consulta</a>
      <a href="/cardapio">Cardápio</a>
      <script src="https://client.crisp.chat/l.js"></script>
    </body></html>
    '''
    data = _page_intelligence(
        source,
        "https://empresa.wixsite.com/site",
        ["https://static.wixstatic.com/site.css", "https://client.crisp.chat/l.js"],
        [("https://empresa.wixsite.com/agendar", "Agendar consulta"), ("https://empresa.wixsite.com/cardapio", "Cardápio")],
        "Agendar consulta Cardápio",
        "",
    )
    assert data["free_host_domain"] is True
    assert "Wix" in data["technologies"]
    assert "Google Analytics" in data["analytics"]
    assert data["booking"] is True
    assert data["catalog_or_menu"] is True
    assert data["live_chat"] is True


def test_deep_audit_persists_compact_site_intelligence_for_score(auth, lead_data, monkeypatch):
    created = auth.post("/api/leads", json=lead_data).json()

    class IntelligenceResearcher(FakeResearcher):
        def deep_audit(self, lead, website_url):
            return {
                "level": "deep",
                "quality_score": 41,
                "website_status": "poor",
                "pages_checked": 3,
                "categories": {},
                "findings": [
                    {"key": "no_cta", "severity": "high", "label": "Sem CTA", "detail": ""},
                    {"key": "slow_response", "severity": "medium", "label": "Lento", "detail": ""},
                ],
                "angles": [],
                "pages": [],
                "signals": {
                    "own_domain": True,
                    "free_host_domain": False,
                    "email": True,
                    "forms": 1,
                    "social": True,
                    "analytics": ["Google Analytics"],
                    "technologies": ["WordPress", "Elementor"],
                    "booking": True,
                    "ecommerce": False,
                    "catalog_or_menu": False,
                    "live_chat": True,
                    "mixed_content": 0,
                },
                "audited_at": 1_700_000_300,
                "fetch_errors": 0,
            }

    monkeypatch.setattr(main, "website_researcher", IntelligenceResearcher())
    response = auth.post(f"/api/leads/{created['id']}/research/deep")
    assert response.status_code == 200, response.text
    lead = response.json()["lead"]
    intelligence = lead["website_intelligence"]
    assert intelligence["quality_score"] == 41
    assert intelligence["high_findings"] == 1
    assert intelligence["email"] is True
    assert intelligence["analytics"] == ["Google Analytics"]
    assert intelligence["technologies"] == ["WordPress", "Elementor"]
    assert intelligence["findings"][0]["key"] == "no_cta"
    assert intelligence["whatsapp_site"] is False
    assert lead["website_analyzed_at"] == 1_700_000_300
    assert lead["score"]["version"] == "3.0"
    assert lead["score"]["dimensions"]["digital_need"]["value"] >= 30
    assert lead["score"]["dimensions"]["reachability"]["value"] == 20


def test_intelligent_reanalysis_selects_web_then_deep_when_evidence_is_sparse(auth, monkeypatch):
    sparse = {
        "name": "Empresa Teste",
        "category": "Clínica odontológica",
        "city": "Recife",
        "country": "BR",
        "latitude": -8.05,
        "longitude": -34.9,
        "website": "",
        "website_status": "unknown",
        "rating": None,
        "reviews": None,
        "instagram": "",
        "instagram_active": False,
        "phone": "",
        "whatsapp": "",
        "potential_cents": 0,
    }
    created = auth.post("/api/leads", json=sparse).json()

    class ReanalysisResearcher(FakeResearcher):
        def deep_audit(self, lead, website_url):
            return {
                "level": "deep",
                "quality_score": 58,
                "website_status": "poor",
                "pages_checked": 3,
                "categories": {},
                "findings": [{"key": "no_cta", "severity": "high", "label": "Sem CTA", "detail": ""}],
                "angles": [],
                "pages": [],
                "signals": {
                    "own_domain": True,
                    "free_host_domain": False,
                    "email": True,
                    "forms": 1,
                    "social": True,
                    "whatsapp": True,
                    "booking": False,
                    "ecommerce": False,
                    "catalog_or_menu": False,
                    "live_chat": False,
                    "mixed_content": 0,
                },
                "audited_at": 1_700_000_500,
                "fetch_errors": 0,
            }

    monkeypatch.setattr(main, "website_researcher", ReanalysisResearcher())
    response = auth.post(f"/api/leads/{created['id']}/reanalysis")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "web_research" in payload["actions"]
    assert "deep_audit" in payload["actions"]
    assert payload["after_confidence"] > payload["before_confidence"]
    assert payload["lead"]["website_status"] == "poor"
    assert payload["research"]["audit_level"] == "deep"


def test_local_competitive_context_uses_nearby_same_niche_peers(auth):
    base = {
        "category": "Clínica odontológica",
        "city": "Recife",
        "country": "BR",
        "rating": 4.6,
        "reviews": 120,
        "instagram": "",
        "instagram_active": False,
        "phone": "+558132323232",
        "whatsapp": "",
        "potential_cents": 0,
    }
    for index in range(4):
        payload = {
            **base,
            "name": f"Clínica Forte {index}",
            "latitude": -8.05 + (index * 0.001),
            "longitude": -34.90 + (index * 0.001),
            "website": f"https://clinicaforte{index}.example.com",
            "website_status": "good",
        }
        response = auth.post("/api/leads", json=payload)
        assert response.status_code == 201, response.text

    target = auth.post("/api/leads", json={
        **base,
        "name": "Clínica Alvo",
        "latitude": -8.052,
        "longitude": -34.902,
        "reviews": 240,
        "website": "https://clinicaalvo.example.com",
        "website_status": "poor",
    })
    assert target.status_code == 201, target.text
    payload = target.json()
    context = payload["competitive_context"]
    assert context["status"] == "ready"
    assert context["peers_count"] >= 4
    assert context["strong_site_rate"] >= 75
    assert context["site_gap"] == "weak"
    assert any(item["key"] == "competitive_site_gap" for item in payload["score"]["reasons"])
