"""ScoutLIQ commercial priority 3.0 with retained technical diagnostics.

Unknown commercial dimensions are explicit. Historical 2.5 contributions remain
available for migration snapshots and technical detail, not as a second priority.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from typing import Any
from urllib.parse import urlparse

RULE_VERSION = "2.5"
DIMENSION_MAX = {
    "digital_need": 50,
    "public_demand": 20,
    "reachability": 20,
    "digital_activity": 10,
}

AGGREGATOR_HOSTS = (
    "linktr.ee", "beacons.ai", "bio.site", "campsite.bio", "taplink.cc",
    "instagram.com", "facebook.com", "wa.me", "whatsapp.com",
)
FREE_HOST_SUFFIXES = (
    "wixsite.com", "wordpress.com", "weebly.com", "webflow.io", "carrd.co",
    "sites.google.com", "my.canva.site", "godaddysites.com", "strikingly.com",
    "square.site", "site123.me", "github.io", "pages.dev", "netlify.app",
    "vercel.app", "web.app", "blogspot.com",
)

SERVICE_LABELS: dict[str, str] = {
    "site_institucional": "Site institucional",
    "landing_page": "Landing page",
    "redesign": "Redesign",
    "sistema_agendamento": "Sistema de agendamento",
    "catalogo": "Catálogo digital",
    "ecommerce": "E-commerce",
    "site_sob_medida": "Site ou sistema sob medida",
    "seo_local": "SEO local",
    "otimizacao": "Otimização de site",
    "sistema_reservas": "Sistema de reservas",
    "cardapio_digital": "Cardápio digital",
}

CONFIDENCE_MAX = {
    "identity": 15,
    "public_evidence": 15,
    "digital_presence": 20,
    "website_verification": 25,
    "contactability": 15,
    "niche_context": 10,
}

# Requirements are deliberately conservative. A missing capability only affects
# the opportunity score after the site has actually been audited.
NICHE_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "key": "healthcare",
        "label": "Saúde e clínicas",
        "keywords": ("clinica", "hospital", "dent", "odont", "fisioter", "psicolog", "medic", "laboratorio", "veterin", "fono", "nutri"),
        "requirements": (
            ("booking", "Agendamento online", "high", 8, "Agendamento online não detectado", "Para este nicho, reduzir atrito entre interesse e marcação costuma ser relevante.", ("sistema_agendamento", "site_institucional")),
            ("forms", "Contato estruturado", "medium", 4, "Canal estruturado de contato não detectado", "Formulário ou fluxo de contato ajuda a captar pedidos além do telefone.", ("site_institucional",)),
        ),
    },
    {
        "key": "food",
        "label": "Alimentação",
        "keywords": ("restaurante", "pizzaria", "hamburg", "lanchonete", "cafeteria", "padaria", "bar ", "bar$", "sushi", "doceria", "confeitaria", "food", "bakery", "restaurant"),
        "requirements": (
            ("catalog_or_menu", "Cardápio ou catálogo", "high", 9, "Cardápio digital não detectado", "Para alimentação, o cliente normalmente precisa consultar oferta e preços antes do contato.", ("cardapio_digital", "site_institucional")),
            ("whatsapp_site", "Contato rápido", "medium", 4, "WhatsApp no site não detectado", "Contato rápido costuma ser parte importante da conversão local neste nicho.", ("site_institucional",)),
        ),
    },
    {
        "key": "beauty",
        "label": "Beleza e estética",
        "keywords": ("barbear", "salao", "beleza", "estetica", "manicure", "cabeleir", "spa", "nail", "beauty"),
        "requirements": (
            ("booking", "Agendamento online", "high", 9, "Agendamento online não detectado", "Serviços com horário marcado ganham valor quando a agenda pode ser acionada diretamente.", ("sistema_agendamento", "site_institucional")),
            ("social", "Prova social conectada", "medium", 3, "Redes sociais não vinculadas ao site", "Portfólio visual e prova social são especialmente relevantes neste nicho.", ("site_institucional",)),
        ),
    },
    {
        "key": "automotive",
        "label": "Automotivo",
        "keywords": ("veiculo", "carro", "automovel", "multimarcas", "concession", "oficina", "mecanica", "auto center", "moto", "seminovo"),
        "requirements": (
            ("catalog_or_menu", "Estoque ou catálogo", "high", 9, "Estoque ou catálogo não detectado", "Quem vende veículos ou peças precisa expor oferta atual sem depender apenas de conversa manual.", ("catalogo", "site_sob_medida")),
            ("whatsapp_site", "Contato rápido", "medium", 4, "WhatsApp no site não detectado", "Contato rápido costuma ser decisivo para consulta de estoque e negociação.", ("site_institucional",)),
        ),
    },
    {
        "key": "retail",
        "label": "Varejo",
        "keywords": ("loja", "varejo", "boutique", "roupa", "calcado", "moveis", "eletron", "acessorio", "store", "shop"),
        "requirements": (
            ("catalog_or_menu", "Catálogo", "high", 7, "Catálogo digital não detectado", "Exibir produtos reduz dependência de atendimento manual para apresentar a oferta.", ("catalogo", "site_sob_medida")),
            ("ecommerce", "Compra online", "medium", 5, "Fluxo de compra online não detectado", "Dependendo da operação, checkout pode ampliar conversão além do contato direto.", ("ecommerce",)),
        ),
    },
    {
        "key": "hospitality",
        "label": "Hospedagem",
        "keywords": ("hotel", "pousada", "hostel", "resort", "hospedagem", "inn"),
        "requirements": (
            ("booking", "Reserva online", "high", 10, "Reserva online não detectada", "Hospedagem depende fortemente de consulta de disponibilidade e reserva.", ("sistema_reservas", "site_sob_medida")),
        ),
    },
    {
        "key": "fitness",
        "label": "Fitness e bem-estar",
        "keywords": ("academia", "crossfit", "pilates", "personal", "fitness", "gym", "studio"),
        "requirements": (
            ("booking", "Aula ou avaliação agendável", "medium", 6, "Agendamento não detectado", "Aula experimental, avaliação ou atendimento podem converter melhor com marcação direta.", ("sistema_agendamento", "site_institucional")),
        ),
    },
    {
        "key": "education",
        "label": "Educação",
        "keywords": ("escola", "colegio", "curso", "faculdade", "idioma", "educacao", "ensino", "school", "college"),
        "requirements": (
            ("forms", "Captação de interesse", "high", 6, "Formulário de interesse não detectado", "Matrículas e pedidos de informação precisam de um caminho claro de captação.", ("landing_page", "site_institucional")),
        ),
    },
    {
        "key": "real_estate",
        "label": "Imobiliário",
        "keywords": ("imobili", "imovel", "corretor", "real estate"),
        "requirements": (
            ("catalog_or_menu", "Catálogo de imóveis", "high", 10, "Catálogo de imóveis não detectado", "O estoque é parte central da experiência de pesquisa neste nicho.", ("catalogo", "site_sob_medida")),
            ("forms", "Captação de interesse", "medium", 4, "Formulário de interesse não detectado", "Formulários ajudam a capturar interesse por imóvel ou perfil de busca.", ("site_sob_medida",)),
        ),
    },
    {
        "key": "professional_services",
        "label": "Serviços profissionais",
        "keywords": ("advoc", "contador", "contabil", "consultor", "arquitet", "engenhar", "agencia", "assessoria", "consultoria"),
        "requirements": (
            ("forms", "Contato estruturado", "high", 5, "Formulário de contato não detectado", "Serviços consultivos precisam de um caminho claro para transformar visita em conversa.", ("site_institucional", "landing_page")),
            ("own_domain", "Domínio próprio", "medium", 5, "Domínio próprio não detectado", "Credibilidade institucional pesa mais para serviços baseados em confiança.", ("site_institucional",)),
        ),
    },
    {
        "key": "home_services",
        "label": "Serviços locais",
        "keywords": ("eletric", "encan", "dedet", "limpeza", "manutenc", "refrigeracao", "ar condicionado", "construc", "pintor", "chaveiro"),
        "requirements": (
            ("whatsapp_site", "Contato rápido", "high", 6, "WhatsApp no site não detectado", "Serviços locais frequentemente dependem de resposta rápida para orçamento.", ("landing_page", "site_institucional")),
        ),
    },
)

FINDING_DIAGNOSIS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "no_https": ("technical", "Site sem HTTPS", "A conexão não usa HTTPS, o que afeta confiança e segurança percebida.", ("redesign",)),
    "no_viewport": ("mobile", "Experiência mobile comprometida", "A auditoria não encontrou viewport responsivo.", ("redesign",)),
    "slow_response": ("performance", "Site lento", "A resposta do site ficou acima da faixa saudável na auditoria.", ("redesign", "otimizacao")),
    "heavy_html": ("performance", "Página muito pesada", "O HTML excedeu o limite usado pela auditoria.", ("redesign", "otimizacao")),
    "mixed_content": ("technical", "Conteúdo inseguro", "Recursos HTTP foram carregados dentro de página HTTPS.", ("redesign",)),
    "weak_title": ("discoverability", "Título de página fraco", "O título não atende aos critérios básicos de descoberta.", ("seo_local", "redesign")),
    "no_description": ("discoverability", "Meta description ausente ou fraca", "A página não apresenta uma descrição adequada nos metadados.", ("seo_local", "redesign")),
    "no_schema": ("discoverability", "Dados estruturados não detectados", "A auditoria não encontrou schema estruturado na página.", ("seo_local",)),
    "no_h1": ("discoverability", "H1 principal ausente", "A página não apresentou um título principal H1.", ("redesign", "seo_local")),
    "no_phone": ("conversion", "Telefone não encontrado no site", "O site não expõe telefone nas páginas auditadas.", ("redesign",)),
    "no_whatsapp": ("conversion", "WhatsApp não encontrado no site", "O site não expõe um atalho de WhatsApp nas páginas auditadas.", ("redesign",)),
    "no_form": ("conversion", "Formulário não encontrado", "Não foi encontrado formulário de contato nas páginas auditadas.", ("landing_page", "site_institucional")),
    "few_ctas": ("conversion", "Poucas ações comerciais claras", "A auditoria detectou apenas uma chamada clara para ação.", ("redesign",)),
    "no_cta": ("conversion", "Nenhuma ação comercial clara", "Não foi detectada chamada clara para contato, reserva, compra ou orçamento.", ("redesign", "landing_page")),
    "no_contact_page": ("conversion", "Página de contato não encontrada", "Não foi encontrada uma página dedicada de contato.", ("site_institucional",)),
    "no_social": ("presence", "Redes sociais não vinculadas", "O site não conecta o visitante aos perfis sociais encontrados pela auditoria.", ("redesign",)),
    "free_host_domain": ("presence", "Site em subdomínio de plataforma", "O site usa endereço hospedado em plataforma em vez de domínio próprio.", ("site_institucional",)),
    "image_alt_low": ("accessibility", "Baixa cobertura de textos alternativos", "Poucas imagens possuem texto alternativo.", ("redesign",)),
    "button_labels_low": ("accessibility", "Botões sem rótulos claros", "A auditoria encontrou botões sem rótulo suficientemente claro.", ("redesign",)),
}


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip()


def _url_host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _has_suffix(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def _profile(lead: Any) -> dict[str, Any]:
    raw = getattr(lead, "website_intelligence_json", "") or ""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _competitive_profile(lead: Any) -> dict[str, Any]:
    raw = getattr(lead, "competitive_context_json", "") or ""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _commercial_signal_profile(lead: Any) -> dict[str, Any]:
    raw = getattr(lead, "commercial_signal_json", "") or ""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _commercial_structure(
    lead: Any,
    profile: dict[str, Any],
    competitive: dict[str, Any],
    signal_profile: dict[str, Any],
) -> dict[str, Any]:
    """Estimate visible commercial structure from observable proxies only.

    This is intentionally not an estimate of revenue, purchasing power or company
    valuation. It describes how much operating structure is visible in the data.
    """
    maxima = {
        "public_traction": 35,
        "operational_structure": 30,
        "digital_maturity": 20,
        "commercial_access": 15,
    }
    components = {key: {"value": 0, "max": maximum} for key, maximum in maxima.items()}
    signals: list[dict[str, Any]] = []

    def add(component: str, key: str, label: str, points: int) -> None:
        remaining = int(components[component]["max"]) - int(components[component]["value"])
        awarded = max(0, min(int(points), remaining))
        if awarded <= 0:
            return
        components[component]["value"] += awarded
        signals.append({"key": key, "label": label, "points": awarded, "component": component})

    reviews = int(getattr(lead, "reviews", 0) or 0)
    rating = float(getattr(lead, "rating", 0) or 0)
    if reviews >= 1000:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 27)
    elif reviews >= 300:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 23)
    elif reviews >= 100:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 18)
    elif reviews >= 50:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 13)
    elif reviews >= 20:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 8)
    elif reviews >= 5:
        add("public_traction", "reviews", f"{reviews} avaliações públicas", 4)
    if reviews >= 20 and rating >= 4.5:
        add("public_traction", "rating", f"Nota pública {rating:.1f}", 4)
    percentile = competitive.get("review_percentile")
    if competitive.get("status") == "ready" and isinstance(percentile, (int, float)) and percentile >= 75:
        add("public_traction", "local_demand", "Demanda acima de boa parte dos concorrentes locais", 4)

    locations = max(1, int(signal_profile.get("brand_locations") or 1))
    if locations >= 3:
        add("operational_structure", "multiple_locations", f"{locations} unidades com o mesmo nome detectadas", 12)
    elif locations >= 2:
        add("operational_structure", "multiple_locations", "Mais de uma unidade detectada", 8)
    if profile.get("own_domain"):
        add("operational_structure", "own_domain", "Domínio próprio", 6)
    if profile.get("analytics"):
        add("operational_structure", "analytics", "Ferramentas de analytics detectadas", 4)
    capabilities = sum(bool(profile.get(key)) for key in ("booking", "ecommerce", "catalog_or_menu", "live_chat"))
    if capabilities >= 3:
        add("operational_structure", "digital_capabilities", "Múltiplas capacidades digitais operacionais", 8)
    elif capabilities >= 1:
        add("operational_structure", "digital_capabilities", "Capacidade digital operacional detectada", 4)

    instagram = str(getattr(lead, "instagram", "") or "")
    if instagram and bool(getattr(lead, "instagram_active", False)):
        add("digital_maturity", "instagram_active", "Instagram ativo confirmado", 8)
    elif instagram:
        add("digital_maturity", "instagram", "Instagram encontrado", 4)
    if profile.get("social"):
        add("digital_maturity", "social_links", "Site conectado às redes sociais", 3)
    if profile.get("own_domain"):
        add("digital_maturity", "owned_presence", "Presença digital própria", 5)
    if profile.get("analytics"):
        add("digital_maturity", "measurement", "Medição digital detectada", 4)

    if str(getattr(lead, "whatsapp", "") or ""):
        add("commercial_access", "whatsapp", "WhatsApp disponível", 6)
    if str(getattr(lead, "phone", "") or ""):
        add("commercial_access", "phone", "Telefone disponível", 4)
    if profile.get("email"):
        add("commercial_access", "email", "E-mail encontrado", 3)
    if int(profile.get("forms") or 0) > 0:
        add("commercial_access", "forms", "Formulário de contato", 2)

    value = min(100, sum(int(item["value"]) for item in components.values()))
    level = "high" if value >= 70 else "medium" if value >= 40 else "low"
    evidence_checks = [
        reviews > 0,
        str(getattr(lead, "website_status", "unknown") or "unknown") != "unknown",
        bool(profile),
        bool(instagram),
        bool(getattr(lead, "phone", "") or getattr(lead, "whatsapp", "")),
        "brand_locations" in signal_profile,
    ]
    evidence_confidence = round(100 * sum(bool(item) for item in evidence_checks) / len(evidence_checks))
    return {
        "value": value,
        "level": level,
        "confidence": evidence_confidence,
        "components": components,
        "signals": signals[:8],
    }


def _commercial_timing(
    lead: Any,
    dimensions: dict[str, dict[str, int]],
    competitive: dict[str, Any],
    signal_profile: dict[str, Any],
    structure: dict[str, Any],
) -> dict[str, Any]:
    """Estimate approach timing from recent observed changes and current pressure.

    Timing is kept separate from opportunity and service fit. It answers whether
    there is an observable reason to pay attention now, not whether a sale will close.
    """
    now = int(time.time())
    ttl = 90 * 86400
    raw_events = signal_profile.get("events") if isinstance(signal_profile.get("events"), list) else []
    signals: list[dict[str, Any]] = []
    value = 0

    event_weights = {
        "reviews_growth_strong": (34, "Crescimento forte de avaliações públicas"),
        "reviews_growth": (20, "Crescimento recente de avaliações públicas"),
        "website_removed": (32, "Site anteriormente detectado deixou de estar disponível"),
        "website_degraded": (26, "Presença web piorou desde a observação anterior"),
        "new_whatsapp": (8, "Novo WhatsApp detectado"),
        "new_phone": (5, "Novo telefone detectado"),
        "new_instagram": (6, "Novo Instagram detectado"),
        "additional_location": (22, "Nova unidade com o mesmo nome foi detectada"),
        "website_new": (-16, "Um site próprio passou a ser detectado"),
        "website_improved": (-10, "A presença web melhorou desde a observação anterior"),
    }
    for event in raw_events[-12:]:
        if not isinstance(event, dict):
            continue
        at = int(event.get("at") or 0)
        if not at or now - at > ttl:
            continue
        key = str(event.get("key") or "")
        if key not in event_weights:
            continue
        points, label = event_weights[key]
        value += points
        detail = str(event.get("detail") or "")[:160]
        signals.append({
            "key": key,
            "label": label,
            "detail": detail,
            "points": abs(points),
            "effect": "positive" if points >= 0 else "negative",
            "at": at,
        })

    digital_need = int(dimensions.get("digital_need", {}).get("value", 0))
    public_demand = int(dimensions.get("public_demand", {}).get("value", 0))
    if competitive.get("status") == "ready" and competitive.get("demand_above_median") and competitive.get("site_gap") in {"missing", "weak"}:
        value += 20
        signals.append({
            "key": "local_pressure",
            "label": "Demanda forte com presença digital abaixo do mercado local",
            "detail": "O contexto local reforça a janela de abordagem.",
            "points": 20,
            "effect": "positive",
            "at": int(getattr(lead, "competitive_analyzed_at", 0) or 0),
        })
    if public_demand >= 12 and digital_need >= 35:
        value += 12
        signals.append({
            "key": "demand_need_gap",
            "label": "Demanda pública forte para uma necessidade digital relevante",
            "detail": "Há tração pública enquanto a lacuna digital continua material.",
            "points": 12,
            "effect": "positive",
            "at": 0,
        })
    if int(structure.get("value") or 0) >= 70 and digital_need >= 30:
        value += 8
        signals.append({
            "key": "structured_gap",
            "label": "Operação aparente estruturada com lacuna digital",
            "detail": "A estrutura visível reduz o risco de priorizar um negócio sem sinais operacionais.",
            "points": 8,
            "effect": "positive",
            "at": 0,
        })

    value = max(0, min(100, value))
    level = "high" if value >= 55 else "medium" if value >= 25 else "low"
    positive = sorted((item for item in signals if item["effect"] == "positive"), key=lambda item: (-int(item["points"]), -int(item.get("at") or 0)))
    negative = sorted((item for item in signals if item["effect"] == "negative"), key=lambda item: (-int(item["points"]), -int(item.get("at") or 0)))
    latest_event_at = max((int(item.get("at") or 0) for item in signals), default=0) or None
    return {
        "value": value,
        "level": level,
        "signals": (positive + negative)[:6],
        "latest_event_at": latest_event_at,
    }


def _combined_signals(
    lead: Any,
    dimensions: dict[str, dict[str, int]],
    confidence: dict[str, Any],
    service_scores: list[dict[str, Any]],
    competitive: dict[str, Any],
    structure: dict[str, Any],
    timing: dict[str, Any],
    signal_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """Combine independent evidence into higher-context commercial signals.

    Combined signals are explanatory patterns, not extra hidden score points.
    They intentionally do not change the Opportunity Score by themselves.
    """
    digital_need = int(dimensions.get("digital_need", {}).get("value", 0))
    public_demand = int(dimensions.get("public_demand", {}).get("value", 0))
    reachability = int(dimensions.get("reachability", {}).get("value", 0))
    confidence_value = int(confidence.get("value") or 0)
    structure_value = int(structure.get("value") or 0)
    timing_value = int(timing.get("value") or 0)
    event_keys = {
        str(item.get("key") or "")
        for item in (signal_profile.get("events") if isinstance(signal_profile.get("events"), list) else [])[-12:]
        if isinstance(item, dict)
    }
    best_service = max(service_scores, key=lambda item: int(item.get("value") or 0), default=None)
    items: list[dict[str, Any]] = []

    def add(key: str, label: str, strength: str, evidence: list[str], action: str) -> None:
        if any(item["key"] == key for item in items):
            return
        items.append({
            "key": key,
            "label": label,
            "strength": strength,
            "evidence": [value for value in evidence if value][:4],
            "recommended_action": action,
        })

    if competitive.get("status") == "ready" and competitive.get("demand_above_median") and competitive.get("site_gap") in {"missing", "weak"}:
        add(
            "local_demand_digital_gap",
            "Demanda local forte com presença digital abaixo do mercado",
            "high" if public_demand >= 10 else "medium",
            [
                f"Demanda pública {public_demand}/20",
                f"Gap local: {competitive.get('site_gap')}",
                f"{int(competitive.get('peers_count') or 0)} concorrentes comparáveis",
            ],
            "Priorizar abordagem baseada na diferença entre demanda e presença digital.",
        )

    growth = bool(event_keys & {"reviews_growth_strong", "reviews_growth", "additional_location"})
    if growth and digital_need >= 30:
        add(
            "growth_without_digital_upgrade",
            "Crescimento recente sem evolução digital equivalente",
            "high" if timing_value >= 55 else "medium",
            [
                "Mudança recente de tração ou estrutura detectada",
                f"Necessidade digital {digital_need}/50",
                f"Timing {timing_value}/100",
            ],
            "Abordar enquanto a expansão ou tração ainda está recente.",
        )

    if event_keys & {"website_removed", "website_degraded"} and public_demand >= 5:
        add(
            "digital_decline_with_demand",
            "Presença digital piorou enquanto existe demanda pública",
            "high",
            ["Site removido ou degradado recentemente", f"Demanda pública {public_demand}/20"],
            "Investigar a mudança e abordar com foco na recuperação da presença digital.",
        )

    if structure_value >= 65 and digital_need >= 30:
        add(
            "structured_business_digital_gap",
            "Operação aparente estruturada com lacuna digital relevante",
            "high" if structure_value >= 75 else "medium",
            [f"Estrutura aparente {structure_value}/100", f"Necessidade digital {digital_need}/50"],
            "Priorizar uma solução compatível com a maturidade operacional observada.",
        )

    if best_service and int(best_service.get("value") or 0) >= 75 and reachability >= 10 and confidence_value >= 65:
        add(
            "qualified_reachable_fit",
            "Fit forte, dados confiáveis e canal de contato disponível",
            "high",
            [
                f"{best_service.get('label')}: {int(best_service.get('value') or 0)}/100",
                f"Confidence {confidence_value}/100",
                f"Contato {reachability}/20",
            ],
            "Levar para abordagem comercial com o serviço de maior fit.",
        )

    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (order.get(str(item.get("strength")), 9), str(item.get("key"))))
    return items[:5]


def _matches(text: str, keyword: str) -> bool:
    if keyword.endswith("$"):
        return text.endswith(keyword[:-1])
    return keyword in text


def niche_context(lead: Any, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Infer a conservative commercial niche from category/name without an LLM."""
    profile = profile or _profile(lead)
    category = _normalized(str(getattr(lead, "category", "") or ""))
    name = _normalized(str(getattr(lead, "name", "") or ""))
    selected: dict[str, Any] | None = None
    matched_term = ""
    matched_by = ""
    for candidate in NICHE_PROFILES:
        for keyword in candidate["keywords"]:
            if _matches(category, keyword):
                selected, matched_term, matched_by = candidate, keyword.rstrip("$"), "category"
                break
        if selected:
            break
    if selected is None:
        for candidate in NICHE_PROFILES:
            for keyword in candidate["keywords"]:
                if _matches(name, keyword):
                    selected, matched_term, matched_by = candidate, keyword.rstrip("$"), "name"
                    break
            if selected:
                break
    if selected is None:
        return {
            "key": "generic",
            "label": "Negócio local",
            "confidence": 35,
            "matched_term": "",
            "matched_by": "fallback",
            "expectations": [],
        }

    audited = int(profile.get("pages_checked") or 0) > 0
    expectations: list[dict[str, Any]] = []
    for signal, label, importance, _points, _issue_title, _detail, _services in selected["requirements"]:
        if signal == "whatsapp_site":
            value = bool(profile.get("whatsapp_site", False))
        elif signal == "forms":
            value = int(profile.get("forms") or 0) > 0
        else:
            value = bool(profile.get(signal, False))
        expectations.append({
            "key": signal,
            "label": label,
            "importance": importance,
            "state": "present" if audited and value else "missing" if audited else "unknown",
        })
    return {
        "key": selected["key"],
        "label": selected["label"],
        "confidence": 92 if matched_by == "category" else 72,
        "matched_term": matched_term,
        "matched_by": matched_by,
        "expectations": expectations,
    }


def _diagnosis(lead: Any, profile: dict[str, Any], niche: dict[str, Any], website_host: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(key: str, area: str, severity: str, title: str, detail: str, evidence: list[str], services: tuple[str, ...] = ()) -> None:
        if key in seen:
            return
        seen.add(key)
        items.append({
            "key": key,
            "area": area,
            "severity": severity,
            "title": title,
            "detail": detail,
            "evidence": evidence,
            "service_hints": list(services),
        })

    website_status = str(getattr(lead, "website_status", "unknown") or "unknown")
    website = str(getattr(lead, "website", "") or "")
    if website_status == "none":
        add("no_website", "presence", "high", "Sem site próprio confirmado", "A empresa não possui site próprio confirmado nas fontes verificadas.", ["website_status:none"], ("site_institucional",))
    elif website_host and _has_suffix(website_host, AGGREGATOR_HOSTS):
        add("aggregator_website", "presence", "high", "Link social no lugar de site próprio", "O endereço informado leva para rede social ou agregador, não para um site próprio.", [website_host], ("site_institucional",))

    raw_findings = profile.get("findings") if isinstance(profile.get("findings"), list) else []
    for raw in raw_findings:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("key") or "")
        mapped = FINDING_DIAGNOSIS.get(key)
        if not mapped:
            continue
        area, title, default_detail, services = mapped
        severity = str(raw.get("severity") or "medium")
        audit_detail = str(raw.get("detail") or "").strip()[:160]
        evidence = [f"audit:{key}"]
        if audit_detail:
            evidence.append(audit_detail)
        add(key, area, severity, title, default_detail, evidence, services)

    # Niche-specific gaps only become diagnoses after a real website audit.
    audited = int(profile.get("pages_checked") or 0) > 0 and bool(website)
    if audited and website_status != "none":
        selected = next((candidate for candidate in NICHE_PROFILES if candidate["key"] == niche.get("key")), None)
        if selected:
            for signal, _label, importance, _points, issue_title, detail, services in selected["requirements"]:
                if any(e['key']==signal and e['state']=='unknown' for e in niche['expectations']):
                    continue
                if signal == "whatsapp_site":
                    present = bool(profile.get("whatsapp_site", False))
                elif signal == "forms":
                    present = int(profile.get("forms") or 0) > 0
                else:
                    present = bool(profile.get(signal, False))
                if present:
                    continue
                add(
                    f"niche_{signal}",
                    "niche_fit",
                    "high" if importance == "high" else "medium",
                    issue_title,
                    detail,
                    [f"niche:{niche.get('key')}", f"audit:{signal}:not_detected"],
                    services,
                )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (severity_order.get(str(item["severity"]), 9), str(item["area"]), str(item["key"])))
    return items[:10]



def _confidence(lead: Any, profile: dict[str, Any], niche: dict[str, Any], website_host: str) -> dict[str, Any]:
    """Measure evidence coverage, not likelihood of sale.

    A high value means the qualification rests on more verified data. Missing
    evidence never reduces the opportunity score; it only lowers confidence.
    """
    components = {key: {"value": 0, "max": maximum} for key, maximum in CONFIDENCE_MAX.items()}
    missing: list[str] = []

    def add(component: str, points: int) -> None:
        remaining = components[component]["max"] - components[component]["value"]
        components[component]["value"] += max(0, min(int(points), int(remaining)))

    if str(getattr(lead, "name", "") or "").strip():
        add("identity", 5)
    else:
        missing.append("Nome da empresa")
    if str(getattr(lead, "category", "") or "").strip():
        add("identity", 5)
    else:
        missing.append("Categoria")
    if str(getattr(lead, "address", "") or "").strip() or str(getattr(lead, "city", "") or "").strip():
        add("identity", 5)
    else:
        missing.append("Localização")

    reviews = int(getattr(lead, "reviews", 0) or 0)
    rating = float(getattr(lead, "rating", 0) or 0)
    if reviews > 0:
        add("public_evidence", 10)
    else:
        missing.append("Volume de avaliações")
    if rating > 0:
        add("public_evidence", 5)
    else:
        missing.append("Nota pública")

    website_status = str(getattr(lead, "website_status", "unknown") or "unknown")
    website = str(getattr(lead, "website", "") or "")
    if website_status != "unknown":
        add("digital_presence", 10)
    else:
        missing.append("Situação do site")
    if website or website_status == "none":
        add("digital_presence", 5)
    if str(getattr(lead, "instagram", "") or ""):
        add("digital_presence", 5)
    else:
        missing.append("Instagram")

    pages_checked = int(profile.get("pages_checked") or 0)
    if website_status == "none":
        # Confirmed absence is itself a complete answer to the website question.
        add("website_verification", 25)
    elif website and pages_checked >= 3:
        add("website_verification", 25)
    elif website and pages_checked >= 1:
        add("website_verification", 18)
        missing.append("Auditoria completa do site")
    elif website_host and _has_suffix(website_host, AGGREGATOR_HOSTS):
        add("website_verification", 18)
        missing.append("Auditoria de site próprio")
    elif website:
        add("website_verification", 6)
        missing.append("Auditoria do site")
    else:
        missing.append("Verificação do site")

    if str(getattr(lead, "whatsapp", "") or ""):
        add("contactability", 6)
    if str(getattr(lead, "phone", "") or ""):
        add("contactability", 5)
    if profile.get("email"):
        add("contactability", 2)
    if int(profile.get("forms") or 0) > 0:
        add("contactability", 2)
    if components["contactability"]["value"] == 0:
        missing.append("Canal de contato verificado")

    matched_by = str(niche.get("matched_by") or "fallback")
    if matched_by == "category":
        add("niche_context", 10)
    elif matched_by == "name":
        add("niche_context", 7)
    else:
        add("niche_context", 2)
        missing.append("Nicho identificado com precisão")

    value = min(100, sum(int(item["value"]) for item in components.values()))
    level = "high" if value >= 80 else "medium" if value >= 55 else "low"
    return {
        "value": value,
        "level": level,
        "components": components,
        "missing": list(dict.fromkeys(missing))[:6],
    }


def _service_scores(
    lead: Any,
    profile: dict[str, Any],
    niche: dict[str, Any],
    diagnosis: list[dict[str, Any]],
    dimensions: dict[str, dict[str, int]],
) -> list[dict[str, Any]]:
    """Derive service-fit scores from verified needs and commercial context.

    These values express how well the observed opportunity fits a service. They
    are not close probabilities and never create a need from missing evidence.
    """
    needs: dict[str, int] = {key: 0 for key in SERVICE_LABELS}
    signals: dict[str, list[str]] = {key: [] for key in SERVICE_LABELS}

    def bump(service: str, points: int, signal: str) -> None:
        if service not in needs or points <= 0:
            return
        before = needs[service]
        needs[service] = min(80, before + int(points))
        if signal and signal not in signals[service]:
            signals[service].append(signal)

    website_status = str(getattr(lead, "website_status", "unknown") or "unknown")
    website = str(getattr(lead, "website", "") or "")
    website_host = _url_host(website)

    # Strong universal website states.
    if website_status == "none":
        bump("site_institucional", 72, "Sem site próprio confirmado")
        if niche.get("key") in {"education", "professional_services", "home_services"}:
            bump("landing_page", 32, "Negócio sem presença própria e com fluxo de captação relevante")
    elif website_host and _has_suffix(website_host, AGGREGATOR_HOSTS):
        bump("site_institucional", 66, "Rede social ou agregador usado no lugar de site próprio")
    elif website_status == "poor":
        bump("redesign", 48, "Site com problemas confirmados")

    if profile.get("free_host_domain") or (website_host and _has_suffix(website_host, FREE_HOST_SUFFIXES)):
        bump("site_institucional", 38, "Site em subdomínio de plataforma")
        bump("redesign", 18, "Estrutura atual limitada por hospedagem de plataforma")

    area_weight = {
        "niche_fit": {"high": 50, "medium": 32, "low": 16},
        "conversion": {"high": 24, "medium": 15, "low": 7},
        "mobile": {"high": 30, "medium": 20, "low": 10},
        "performance": {"high": 28, "medium": 18, "low": 8},
        "technical": {"high": 18, "medium": 11, "low": 5},
        "discoverability": {"high": 24, "medium": 14, "low": 7},
        "presence": {"high": 34, "medium": 20, "low": 10},
        "accessibility": {"high": 14, "medium": 8, "low": 4},
    }
    # Some findings have a clearer service implication than their generic area.
    explicit_weights: dict[str, dict[str, int]] = {
        "no_viewport": {"redesign": 32},
        "slow_response": {"otimizacao": 34, "redesign": 12},
        "heavy_html": {"otimizacao": 24, "redesign": 8},
        "no_cta": {"landing_page": 28, "redesign": 20},
        "few_ctas": {"landing_page": 14, "redesign": 10},
        "no_form": {"landing_page": 22, "site_institucional": 14},
        "no_contact_page": {"site_institucional": 18},
        "weak_title": {"seo_local": 16},
        "no_description": {"seo_local": 14},
        "no_schema": {"seo_local": 18},
        "no_h1": {"seo_local": 14, "redesign": 6},
        "no_https": {"redesign": 16},
        "mixed_content": {"redesign": 12},
        "image_alt_low": {"redesign": 8},
        "button_labels_low": {"redesign": 8},
    }

    handled_presence = {"no_website", "aggregator_website", "free_host_domain"}
    for item in diagnosis:
        key = str(item.get("key") or "")
        if key in handled_presence:
            continue
        severity = str(item.get("severity") or "medium")
        area = str(item.get("area") or "")
        title = str(item.get("title") or key)
        hints = [str(value) for value in item.get("service_hints") or []]
        overrides = explicit_weights.get(key, {})
        for index, service in enumerate(hints):
            if service in overrides:
                points = overrides[service]
            else:
                points = int(area_weight.get(area, {}).get(severity, 8))
                if area == "niche_fit" and index > 0:
                    # The first niche hint is the specific product fit; later hints
                    # are supporting options and should not inherit the same weight.
                    points = max(12, round(points * 0.52))
            bump(service, points, title)
        for service, points in overrides.items():
            if service not in hints:
                bump(service, points, title)

    # Niche-specific aliases: one audited gap can point to a more precise product.
    diagnosis_keys = {str(item.get("key") or "") for item in diagnosis}
    niche_key = str(niche.get("key") or "generic")
    if "niche_booking" in diagnosis_keys:
        if niche_key == "hospitality":
            bump("sistema_reservas", 58, "Reserva online relevante para hospedagem")
        else:
            bump("sistema_agendamento", 58, "Agendamento relevante para este nicho")
    if "niche_catalog_or_menu" in diagnosis_keys:
        if niche_key == "food":
            bump("cardapio_digital", 62, "Cardápio digital relevante para alimentação")
        else:
            bump("catalogo", 58, "Catálogo relevante para este nicho")
    if "niche_ecommerce" in diagnosis_keys:
        bump("ecommerce", 58, "Compra online relevante para este varejo")

    # Complex niche gaps can justify a custom build, but only after verified audit.
    complex_gap_count = sum(1 for key in diagnosis_keys if key.startswith("niche_"))
    if complex_gap_count >= 2 and niche_key in {"automotive", "retail", "real_estate", "hospitality"}:
        bump("site_sob_medida", min(46, 24 + complex_gap_count * 10), "Múltiplas capacidades do nicho não foram detectadas")

    public = int(dimensions.get("public_demand", {}).get("value", 0))
    reachable = int(dimensions.get("reachability", {}).get("value", 0))
    commercial_context = min(20, round((public / 20) * 12 + (reachable / 20) * 8))

    result: list[dict[str, Any]] = []
    for key, need in needs.items():
        if need <= 0:
            continue
        value = min(100, need + commercial_context)
        result.append({
            "key": key,
            "label": SERVICE_LABELS[key],
            "value": value,
            "need": need,
            "commercial_context": commercial_context,
            "signals": signals[key][:4],
        })
    result.sort(key=lambda item: (-int(item["value"]), -int(item["need"]), str(item["label"])))
    return result

def _technical_score(lead: Any, verified_only: bool = False) -> dict[str, Any]:
    profile = _profile(lead)
    niche = niche_context(lead, profile)
    observed = profile.get('_observed_fields', list(profile))
    if verified_only:
        for expectation in niche['expectations']:
            if expectation['key'] not in observed: expectation['state'] = 'unknown'
    reasons: list[dict[str, Any]] = []
    dimensions = {key: {"value": 0, "max": maximum} for key, maximum in DIMENSION_MAX.items()}

    def add(dimension: str, key: str, label: str, points: int) -> None:
        if points <= 0:
            return
        remaining = dimensions[dimension]["max"] - dimensions[dimension]["value"]
        awarded = min(int(points), int(remaining))
        if awarded <= 0:
            return
        dimensions[dimension]["value"] += awarded
        reasons.append({
            "dimension": dimension,
            "key": key,
            "label": label,
            "points": awarded,
        })

    # 1) Digital need. Confirmed absence is the strongest universal website signal.
    website_status = str(getattr(lead, "website_status", "unknown") or "unknown")
    website = str(getattr(lead, "website", "") or "")
    website_host = _url_host(website)
    if website_status == "none":
        add("digital_need", "no_website", "Sem site confirmado", 50)
    elif website_status == "poor":
        quality = profile.get("quality_score")
        high_findings = int(profile.get("high_findings") or 0)
        medium_findings = int(profile.get("medium_findings") or 0)
        points = 30
        if isinstance(quality, (int, float)):
            points = max(30, min(44, 30 + round(max(0, 65 - float(quality)) * 0.4)))
        points += min(6, high_findings * 2 + medium_findings // 3)
        add("digital_need", "poor_website", "Site com problemas confirmados", min(50, points))
    elif website_host and _has_suffix(website_host, AGGREGATOR_HOSTS):
        add("digital_need", "aggregator_website", "Link social/agregador no lugar de site próprio", 42)
    elif not website and str(getattr(lead, "source", "")) in ("openstreetmap", "geoapify"):
        add("digital_need", "website_unlisted", "Site não informado na fonte de dados", 10)

    if profile.get("free_host_domain") or (website_host and _has_suffix(website_host, FREE_HOST_SUFFIXES)):
        add("digital_need", "free_host_domain", "Site em subdomínio de plataforma", 8)
    if profile.get("mixed_content", 0):
        add("digital_need", "mixed_content", "Conteúdo inseguro detectado no site", 3)

    # Niche context is applied only when the site was actually audited. This lets a
    # good generic site still surface as an opportunity when it misses a capability
    # that is materially relevant for that business model.
    audited = int(profile.get("pages_checked") or 0) > 0 and bool(website)
    if audited and website_status != "none":
        selected = next((candidate for candidate in NICHE_PROFILES if candidate["key"] == niche.get("key")), None)
        if selected:
            for signal, label, _importance, points, issue_title, _detail, _services in selected["requirements"]:
                if verified_only and signal not in observed:
                    continue
                if signal == "whatsapp_site":
                    present = bool(profile.get("whatsapp_site", False))
                elif signal == "forms":
                    present = int(profile.get("forms") or 0) > 0
                else:
                    present = bool(profile.get(signal, False))
                if not present:
                    add("digital_need", f"niche_{signal}", issue_title, points)

    # Local competitive context can strengthen a verified digital gap, but never
    # creates one by itself. It is intentionally capped and only used when the
    # peer sample is large enough to be meaningful.
    competitive = _competitive_profile(lead)
    if competitive.get("status") == "ready" and int(competitive.get("peers_count") or 0) >= 4:
        gap = str(competitive.get("site_gap") or "")
        if gap == "missing":
            add("digital_need", "competitive_site_gap", "Concorrentes locais têm presença própria mais forte", 6)
        elif gap == "weak":
            add("digital_need", "competitive_site_gap", "Site abaixo do padrão digital local", 5)
        if bool(competitive.get("demand_above_median")) and gap in {"missing", "weak"}:
            add("digital_need", "competitive_demand_gap", "Demanda pública forte para uma presença digital abaixo do mercado local", 2)

    # 2) Public demand. Rating only matters with enough public evidence.
    reviews = int(getattr(lead, "reviews", 0) or 0)
    rating = float(getattr(lead, "rating", 0) or 0)
    if reviews >= 1000:
        add("public_demand", "reviews", f"{reviews} avaliações", 14)
    elif reviews >= 300:
        add("public_demand", "reviews", f"{reviews} avaliações", 12)
    elif reviews >= 100:
        add("public_demand", "reviews", f"{reviews} avaliações", 10)
    elif reviews >= 50:
        add("public_demand", "reviews", f"{reviews} avaliações", 7)
    elif reviews >= 20:
        add("public_demand", "reviews", f"{reviews} avaliações", 5)
    elif reviews >= 5:
        add("public_demand", "reviews", f"{reviews} avaliações", 2)

    if reviews >= 20:
        if rating >= 4.7:
            add("public_demand", "rating", f"Nota {rating:.1f}", 6)
        elif rating >= 4.5:
            add("public_demand", "rating", f"Nota {rating:.1f}", 5)
        elif rating >= 4.2:
            add("public_demand", "rating", f"Nota {rating:.1f}", 3)
        elif rating >= 4.0:
            add("public_demand", "rating", f"Nota {rating:.1f}", 1)

    # 3) Reachability. Prefer channels that make an actual commercial approach possible.
    if getattr(lead, "whatsapp", ""):
        add("reachability", "whatsapp", "WhatsApp disponível", 10)
    if getattr(lead, "phone", ""):
        add("reachability", "phone", "Telefone disponível", 6)
    if profile.get("email"):
        add("reachability", "email", "E-mail encontrado no site", 2)
    if profile.get("forms", 0):
        add("reachability", "contact_form", "Formulário de contato disponível", 2)

    # 4) Digital activity/maturity. This shows that the business is active enough to qualify.
    instagram = str(getattr(lead, "instagram", "") or "")
    if instagram and bool(getattr(lead, "instagram_active", False)):
        add("digital_activity", "instagram_active", "Instagram ativo confirmado", 6)
    elif instagram:
        add("digital_activity", "instagram_presence", "Instagram encontrado", 3)

    if profile.get("social"):
        add("digital_activity", "site_social", "Site conectado a redes sociais", 1)
    if profile.get("analytics"):
        add("digital_activity", "analytics", "Analytics detectado", 1)
    if profile.get("own_domain"):
        add("digital_activity", "own_domain", "Domínio próprio detectado", 2)

    value = min(100, sum(int(item["value"]) for item in dimensions.values()))
    diagnosis = _diagnosis(lead, profile, niche, website_host)
    confidence = _confidence(lead, profile, niche, website_host)
    service_scores = _service_scores(lead, profile, niche, diagnosis, dimensions)
    signal_profile = _commercial_signal_profile(lead)
    commercial_structure = _commercial_structure(lead, profile, competitive, signal_profile)
    timing = _commercial_timing(lead, dimensions, competitive, signal_profile, commercial_structure)
    combined_signals = _combined_signals(
        lead,
        dimensions,
        confidence,
        service_scores,
        competitive,
        commercial_structure,
        timing,
        signal_profile,
    )
    return {
        "value": value,
        "reasons": reasons,
        "dimensions": dimensions,
        "niche": niche,
        "diagnosis": diagnosis,
        "confidence": confidence,
        "service_scores": service_scores,
        "competitive": competitive if competitive.get("status") else None,
        "commercial_structure": commercial_structure,
        "timing": timing,
        "combined_signals": combined_signals,
        "version": RULE_VERSION,
    }


def score(lead: Any) -> dict[str, Any]:
    """Commercial priority 3.0. Unknown dimensions are null, never negative facts.

    Values are weighted over observed dimensions, with explicit evidence gates.
    Technical diagnostics retain their historical contract for existing screens.
    """
    from .commercial_fit import assess, facts
    result = _technical_score(lead, verified_only=True)
    profile, data, fit = _profile(lead), facts(lead), assess(lead)
    dims = {}
    def dimension(key, weight, value, reason, state=None):
        dims[key] = {'value': value, 'max': 100, 'weight': weight,
                     'state': state or ('uninvestigated' if value is None else 'verified' if value >= 50 else 'unfavorable'), 'reason': reason}
    dimension('target_fit', 25, 0 if fit['status']=='incompatible' else 85 if fit['independence']=='independent' else 65 if fit['status']=='compatible' else None,
              fit['reasons'][0]['label'])
    status = str(getattr(lead, 'website_status', 'unknown') or 'unknown')
    audited = int(profile.get('pages_checked') or 0) > 0
    gaps = [r for r in result['reasons'] if r['key'].startswith('niche_') and r['key'][6:] in profile]
    contradictory = status == 'none' and bool(getattr(lead, 'website', ''))
    stale = bool(getattr(lead,'website_analyzed_at',0) and time.time()-lead.website_analyzed_at>90*86400)
    need = None if contradictory or stale else 95 if status == 'none' else 80 if status == 'poor' and audited else 65 if gaps and audited else 15 if status == 'good' and audited else None
    dimension('need', 25, need, 'Análise com mais de 90 dias; verificar novamente.' if stale else 'Ausência registrada de site.' if status=='none' and not contradictory else 'Análise das páginas consultadas.' if audited else 'Site ainda não verificado.', 'contradictory' if contradictory else None)
    niche = result['niche'].get('key', 'general')
    impact = 80 if need and need >= 65 and niche not in ('general', 'generic') else 60 if need and need >= 65 else 20 if need is not None else None
    if impact is not None and need is not None and need>=65 and int(getattr(lead,'reviews',0) or 0)>=100 and float(getattr(lead,'rating',0) or 0)>=4.5:
        impact=min(100,impact+20)
    dimension('impact', 20, impact, 'Potencial estimado a partir da lacuna e do setor; não representa receita garantida.' if impact is not None else 'Investigar a necessidade antes de estimar impacto.')
    contact = bool(getattr(lead, 'phone', '') or getattr(lead, 'whatsapp', '') or profile.get('email') or profile.get('forms'))
    blocked = bool(getattr(lead, 'contact_blocked', False))
    dimension('viability', 20, 0 if blocked else 80 if contact else None, 'Contato bloqueado.' if blocked else 'Canal público disponível; envio exige autorização própria.' if contact else 'Canal comercial não verificado.')
    active = bool(getattr(lead, 'instagram_active', False) and getattr(lead, 'instagram', '')) or data.get('operating_status') == 'active'
    dimension('activity', 10, 90 if active else 55 if audited and not stale else 0 if data.get('operating_status') == 'closed' else None,
              'Atividade registrada.' if active else 'Site acessível; atividade operacional não confirmada.' if audited else 'Atividade recente não verificada.')
    from .score_criteria import configuration, commercial_priority
    criteria, criteria_version = configuration(lead)
    result.update(commercial_priority(dims, fit, criteria), version=criteria_version, commercial_fit=fit)
    try:
        result['previous'] = json.loads(getattr(lead, 'previous_score_json', '{}') or '{}')
    except (ValueError, TypeError):
        result['previous'] = {}
    return result
