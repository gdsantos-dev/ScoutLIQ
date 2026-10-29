"""Evidence-based public web research for ScoutLIQ leads.

The researcher is intentionally conservative: it may suggest or confirm a website,
but it only writes back a URL when multiple public signals support that the site
belongs to the selected business. No LLM is required for this first layer.
"""
from __future__ import annotations

import html as html_lib
import ipaddress
import json
import os
import re
import socket
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import ORIGIN
from .consumption import metered, submit


BLOCKED_HOST_SUFFIXES = (
    "instagram.com",
    "facebook.com",
    "fb.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "google.com",
    "google.com.br",
    "googleusercontent.com",
    "g.page",
    "maps.app.goo.gl",
    "goo.gl",
    "tripadvisor.com",
    "tripadvisor.com.br",
    "yelp.com",
    "foursquare.com",
    "linktr.ee",
    "wa.me",
    "whatsapp.com",
)

COUNTRY_TLDS: dict[str, tuple[str, ...]] = {
    "BR": ("com.br", "com"),
    "US": ("com", "us"),
    "PT": ("pt", "com.pt", "com"),
    "ES": ("es", "com"),
    "AR": ("com.ar", "com"),
    "MX": ("com.mx", "com"),
    "GB": ("co.uk", "com"),
    "UK": ("co.uk", "com"),
    "CA": ("ca", "com"),
    "AU": ("com.au", "com"),
    "DE": ("de", "com"),
    "FR": ("fr", "com"),
    "IT": ("it", "com"),
}

GENERIC_NAME_TOKENS = {
    "loja", "store", "shop", "filial", "unidade", "unit", "branch", "sucursal",
    "oficial", "official", "empresa", "company", "ltda", "ltd", "llc", "inc",
    "eireli", "sa", "s", "a",
}


class ResearchError(RuntimeError):
    pass


class SearchConfigurationError(ResearchError):
    pass


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.links: list[tuple[str, str]] = []
        self._anchors: list[dict[str, Any]] = []
        self.text_parts: list[str] = []
        self.json_ld: list[str] = []
        self._in_json_ld = False
        self._json_parts: list[str] = []
        self.html_lang = ""
        self.canonical_url = ""
        self.has_favicon = False
        self.resources: list[str] = []
        self.form_count = 0
        self.h1_count = 0
        self.image_count = 0
        self.image_alt_count = 0
        self.button_count = 0
        self.labeled_button_count = 0
        self._button_depth = 0
        self._button_has_label = False
        self._button_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag == "html":
            self.html_lang = data.get("lang", "")[:20]
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (data.get("name") or data.get("property") or "").lower()
            value = data.get("content", "").strip()
            if key and value and key not in self.meta:
                self.meta[key] = value[:1000]
        elif tag == "a":
            href = data.get("href", "").strip()
            self._anchors.append({"href": href[:1000], "parts": [data.get("aria-label", "")[:160]]})
        elif tag == "link":
            href = data.get("href", "").strip()
            rel = {part.strip().lower() for part in data.get("rel", "").split() if part.strip()}
            if "canonical" in rel and href and not self.canonical_url:
                self.canonical_url = href[:1000]
            if rel.intersection({"icon", "shortcut", "apple-touch-icon"}) and href:
                self.has_favicon = True
            if href:
                self.resources.append(href[:1000])
        elif tag == "img":
            self.image_count += 1
            if data.get("alt", "").strip():
                self.image_alt_count += 1
            if data.get("src", "").strip():
                self.resources.append(data["src"].strip()[:1000])
        elif tag == "script":
            if data.get("src", "").strip():
                self.resources.append(data["src"].strip()[:1000])
            if data.get("type", "").lower() == "application/ld+json":
                self._in_json_ld = True
                self._json_parts = []
        elif tag == "form":
            self.form_count += 1
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "button":
            self.button_count += 1
            self._button_depth += 1
            self._button_has_label = bool(data.get("aria-label", "").strip() or data.get("title", "").strip())
            self._button_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._anchors:
            item = self._anchors.pop()
            href = str(item.get("href") or "").strip()
            label = " ".join(str(part).strip() for part in item.get("parts", []) if str(part).strip())[:240]
            if href:
                self.links.append((href, label))
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            payload = " ".join(self._json_parts).strip()
            if payload:
                self.json_ld.append(payload[:100_000])
            self._json_parts = []
        elif tag == "button" and self._button_depth:
            if self._button_has_label or " ".join(self._button_text).strip():
                self.labeled_button_count += 1
            self._button_depth = max(0, self._button_depth - 1)
            self._button_has_label = False
            self._button_text = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title = (self.title + " " + text).strip()[:500]
        elif self._in_json_ld:
            self._json_parts.append(text)
        else:
            if self._anchors:
                self._anchors[-1]["parts"].append(text[:240])
            if self._button_depth:
                self._button_text.append(text[:240])
            if len(" ".join(self.text_parts)) < 120_000:
                self.text_parts.append(text)


@dataclass
class PageSnapshot:
    requested_url: str
    final_url: str
    title: str
    description: str
    text: str
    html_lang: str
    has_viewport: bool
    has_canonical: bool
    has_schema: bool
    has_favicon: bool
    generator: str
    phone_links: list[str]
    email_links: list[str]
    whatsapp_links: list[str]
    instagram_links: list[str]
    social_links: list[str]
    links: list[tuple[str, str]]
    form_count: int
    h1_count: int
    image_count: int
    image_alt_count: int
    button_count: int
    labeled_button_count: int
    mixed_content_count: int
    elapsed_ms: int
    body_bytes: int
    truncated: bool
    technologies: list[str] = field(default_factory=list)
    analytics: list[str] = field(default_factory=list)
    free_host_domain: bool = False
    booking: bool = False
    ecommerce: bool = False
    catalog_or_menu: bool = False
    live_chat: bool = False


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        target = urljoin(req.full_url, newurl)
        _validate_public_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalized(value))


def _host(value: str) -> str:
    try:
        return (urlparse(value).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _display_domain(value: str) -> str:
    host = _host(value)
    return host[4:] if host.startswith("www.") else host


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _name_tokens(name: str) -> list[str]:
    clean = re.sub(r"\([^)]*\)", " ", _normalized(name))
    tokens = [t for t in re.findall(r"[a-z0-9]+", clean) if len(t) > 1 and t not in GENERIC_NAME_TOKENS]
    return tokens[:8]


def candidate_domains(name: str, country: str) -> list[str]:
    tokens = _name_tokens(name)
    if not tokens:
        return []
    bases: list[str] = []
    joined = "".join(tokens)
    if len(joined) >= 4:
        bases.append(joined)
    if len(tokens) >= 2:
        bases.append("".join(tokens[:2]))
        bases.append("-".join(tokens[:2]))
    bases.append(tokens[0])
    bases = list(dict.fromkeys(base for base in bases if 4 <= len(base.replace("-", "")) <= 45))[:4]
    tlds = COUNTRY_TLDS.get((country or "").upper())
    if not tlds:
        cc = (country or "").lower()
        tlds = tuple(x for x in ("com", cc if len(cc) == 2 else "") if x)
    urls: list[str] = []
    for base in bases:
        for tld in tlds[:2]:
            urls.append(f"https://{base}.{tld}")
            urls.append(f"https://www.{base}.{tld}")
    return list(dict.fromkeys(urls))[:10]


def _blocked_host(host: str) -> bool:
    host = host.lower().rstrip(".")
    # Google Sites is a real hosted website and should be inspectable even though google.com is blocked generally.
    if host == "sites.google.com" or host.endswith(".sites.google.com"):
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ResearchError("URL pública inválida.")
    if parsed.port not in (None, 80, 443):
        raise ResearchError("Porta não permitida.")
    host = parsed.hostname.rstrip(".")
    if host.lower() == "localhost" or host.endswith(".local"):
        raise ResearchError("Host não público.")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ResearchError("Domínio não resolvido.") from exc
    addresses = {item[4][0] for item in infos}
    if not addresses:
        raise ResearchError("Domínio não resolvido.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError as exc:
            raise ResearchError("Endereço inválido.") from exc
        if not ip.is_global:
            raise ResearchError("Destino não público.")



FREE_HOST_SUFFIXES = (
    "wixsite.com", "wordpress.com", "weebly.com", "webflow.io", "carrd.co",
    "sites.google.com", "my.canva.site", "godaddysites.com", "strikingly.com",
    "square.site", "site123.me", "github.io", "pages.dev", "netlify.app",
    "vercel.app", "web.app", "blogspot.com",
)


def _host_has_suffix(host: str, suffixes: tuple[str, ...]) -> bool:
    host = (host or "").lower().rstrip(".")
    return any(host == suffix or host.endswith("." + suffix) for suffix in suffixes)


def _page_intelligence(source: str, final_url: str, resources: list[str], links: list[tuple[str, str]], text: str, generator: str) -> dict[str, Any]:
    """Conservative feature/technology detection from the HTML already fetched.

    Detection means "observed in the analyzed HTML", never proof of absence when false.
    """
    haystack = _normalized(" ".join([source[:600_000], generator, *resources[:300]]))
    link_text = _normalized(" ".join(f"{url} {label}" for url, label in links[:300]))
    body = _normalized(text[:120_000])
    combined = f"{haystack} {link_text} {body}"

    technologies: list[str] = []
    analytics: list[str] = []

    def tech(label: str, *needles: str) -> None:
        if any(_normalized(needle) in combined for needle in needles):
            technologies.append(label)

    tech("WordPress", "wp-content", "wordpress")
    tech("WooCommerce", "woocommerce")
    tech("Elementor", "elementor")
    tech("Wix", "wixstatic", "wixsite")
    tech("Shopify", "cdn.shopify.com", "shopify")
    tech("Squarespace", "squarespace")
    tech("Webflow", "webflow")
    tech("Next.js", "/_next/", "__next_data__")
    tech("Bootstrap", "bootstrap.min.css", "bootstrap.min.js")

    if "googletagmanager.com/gtm.js" in source.casefold() or "google tag manager" in combined:
        analytics.append("Google Tag Manager")
    if any(token in source.casefold() for token in ("google-analytics.com", "googletagmanager.com/gtag/js", "gtag(")):
        analytics.append("Google Analytics")
    if "connect.facebook.net" in source.casefold() and "fbq(" in source.casefold():
        analytics.append("Meta Pixel")

    booking_terms = (
        "agendar", "agendamento", "agenda online", "booking", "book now", "appointment",
        "calendly", "doctoralia", "simplybook", "setmore", "trinks",
    )
    ecommerce_terms = ("checkout", "carrinho", "cart", "comprar agora", "buy now", "woocommerce", "shopify")
    catalog_terms = ("cardapio", "cardápio", "menu", "catalogo", "catálogo", "catalog", "produtos", "products")
    chat_terms = ("tawk.to", "jivochat", "jivo", "crisp.chat", "intercom", "zendesk", "livechat")

    return {
        "technologies": list(dict.fromkeys(technologies))[:12],
        "analytics": list(dict.fromkeys(analytics))[:6],
        "free_host_domain": _host_has_suffix(_host(final_url), FREE_HOST_SUFFIXES),
        "booking": any(_normalized(term) in combined for term in booking_terms),
        "ecommerce": any(_normalized(term) in combined for term in ecommerce_terms),
        "catalog_or_menu": any(_normalized(term) in combined for term in catalog_terms),
        "live_chat": any(_normalized(term) in combined for term in chat_terms),
    }

@metered('website')
def _fetch_page(url: str, *, timeout: float, user_agent: str) -> PageSnapshot:
    _validate_public_url(url)
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.4",
            "Accept-Language": "pt-BR,pt;q=0.8,en;q=0.6,es;q=0.5",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    opener = build_opener(_SafeRedirectHandler())
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            final_url = response.geturl()
            _validate_public_url(final_url)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise ResearchError("A URL não retornou HTML.")
            payload = response.read(600_001)
            truncated = len(payload) > 600_000
            if truncated:
                payload = payload[:600_000]
            charset = response.headers.get_content_charset() or "utf-8"
    except HTTPError as exc:
        raise ResearchError(f"HTTP {exc.code}") from exc
    except (URLError, TimeoutError, socket.timeout) as exc:
        raise ResearchError("Site indisponível.") from exc
    elapsed = int((time.monotonic() - started) * 1000)
    try:
        source = payload.decode(charset, errors="replace")
    except LookupError:
        source = payload.decode("utf-8", errors="replace")
    parser = _PageParser()
    try:
        parser.feed(source)
    except Exception:
        pass
    absolute_links = [(urljoin(final_url, href), label) for href, label in parser.links]
    phone_links = [href for href, _ in absolute_links if href.lower().startswith("tel:")]
    email_links = [href for href, _ in absolute_links if href.lower().startswith("mailto:")]
    whatsapp_links = [href for href, _ in absolute_links if _host(href).removeprefix('www.') in ('wa.me','api.whatsapp.com','web.whatsapp.com')]
    instagram_links = [href for href, _ in absolute_links if _host(href).removeprefix('www.') == 'instagram.com']
    social_hosts = ("instagram.com", "facebook.com", "linkedin.com", "youtube.com", "tiktok.com", "x.com", "twitter.com")
    social_links = [href for href, _ in absolute_links if _host_has_suffix(_host(href), social_hosts)]
    mixed_content = 0
    if urlparse(final_url).scheme == "https":
        for resource in parser.resources:
            absolute = urljoin(final_url, resource)
            if urlparse(absolute).scheme == "http":
                mixed_content += 1
    intelligence = _page_intelligence(source, final_url, parser.resources, absolute_links, " ".join(parser.text_parts), parser.meta.get("generator", ""))
    return PageSnapshot(
        requested_url=url,
        final_url=final_url,
        title=html_lib.unescape(parser.title).strip(),
        description=html_lib.unescape(parser.meta.get("description", "")).strip(),
        text=" ".join(parser.text_parts)[:120_000],
        html_lang=parser.html_lang,
        has_viewport=bool(parser.meta.get("viewport")),
        has_canonical=bool(parser.canonical_url),
        has_schema=bool(parser.json_ld),
        has_favicon=parser.has_favicon,
        generator=parser.meta.get("generator", "")[:160],
        phone_links=phone_links[:12],
        email_links=email_links[:12],
        whatsapp_links=whatsapp_links[:8],
        instagram_links=instagram_links[:8],
        social_links=social_links[:16],
        links=absolute_links[:300],
        form_count=parser.form_count,
        h1_count=parser.h1_count,
        image_count=parser.image_count,
        image_alt_count=parser.image_alt_count,
        button_count=parser.button_count,
        labeled_button_count=parser.labeled_button_count,
        mixed_content_count=mixed_content,
        elapsed_ms=elapsed,
        body_bytes=len(payload),
        truncated=truncated,
        technologies=intelligence["technologies"],
        analytics=intelligence["analytics"],
        free_host_domain=bool(intelligence["free_host_domain"]),
        booking=bool(intelligence["booking"]),
        ecommerce=bool(intelligence["ecommerce"]),
        catalog_or_menu=bool(intelligence["catalog_or_menu"]),
        live_chat=bool(intelligence["live_chat"]),
    )


def _identity_score(lead: Any, page: PageSnapshot, *, search_hint: bool = False) -> tuple[int, list[dict[str, Any]]]:
    tokens = _name_tokens(str(getattr(lead, "name", "")))
    title_text = _normalized(f"{page.title} {page.description}")
    body_text = _normalized(page.text[:80_000])
    combined = f"{title_text} {body_text}"
    domain_slug = _slug(_display_domain(page.final_url).split(".", 1)[0])
    name_joined = "".join(tokens)
    evidence: list[dict[str, Any]] = []
    score = 0

    if tokens:
        matched = [token for token in tokens if token in combined]
        ratio = len(matched) / max(1, len(tokens))
        if ratio >= 0.75:
            score += 34
            evidence.append({"key": "name_match", "value": f"{len(matched)}/{len(tokens)}"})
        elif ratio >= 0.5:
            score += 22
            evidence.append({"key": "name_partial", "value": f"{len(matched)}/{len(tokens)}"})
        if name_joined and (name_joined in domain_slug or domain_slug in name_joined) and len(domain_slug) >= 5:
            score += 28
            evidence.append({"key": "domain_match", "value": _display_domain(page.final_url)})

    city = _normalized(str(getattr(lead, "city", ""))).strip()
    if city and city in combined:
        score += 10
        evidence.append({"key": "city_match", "value": str(getattr(lead, "city", ""))})

    lead_phone = _digits(str(getattr(lead, "phone", "")))
    page_digits = _digits(" ".join([page.text[:80_000], *page.phone_links, *page.whatsapp_links]))
    if len(lead_phone) >= 8 and lead_phone[-8:] in page_digits:
        score += 24
        evidence.append({"key": "phone_match", "value": lead_phone[-8:]})

    address = _normalized(str(getattr(lead, "address", "")))
    address_tokens = [t for t in re.findall(r"[a-z0-9]+", address) if len(t) >= 4][:5]
    address_hits = [t for t in address_tokens if t in combined]
    if address_tokens and len(address_hits) >= min(2, len(address_tokens)):
        score += 12
        evidence.append({"key": "address_match", "value": ", ".join(address_hits[:3])})

    instagram = _host(str(getattr(lead, "instagram", "")))
    if instagram and any(_host(link) == instagram for link in page.instagram_links):
        score += 8
        evidence.append({"key": "instagram_match", "value": "Instagram"})

    if search_hint:
        score += 6
        evidence.append({"key": "search_result", "value": "web"})

    return min(100, score), evidence


def _search_result_score(lead: Any, item: dict[str, str]) -> tuple[int, list[dict[str, Any]]]:
    url = item.get("url", "")
    text = _normalized(f"{item.get('title','')} {item.get('description','')}")
    tokens = _name_tokens(str(getattr(lead, "name", "")))
    domain_slug = _slug(_display_domain(url).split(".", 1)[0])
    joined = "".join(tokens)
    score = 0
    evidence: list[dict[str, Any]] = [{"key": "search_result", "value": "web"}]
    if joined and len(domain_slug) >= 5 and (joined in domain_slug or domain_slug in joined):
        score += 38
        evidence.append({"key": "domain_match", "value": _display_domain(url)})
    if tokens:
        matched = [token for token in tokens if token in text]
        ratio = len(matched) / max(1, len(tokens))
        if ratio >= 0.75:
            score += 32
            evidence.append({"key": "name_match", "value": f"{len(matched)}/{len(tokens)}"})
        elif ratio >= 0.5:
            score += 20
            evidence.append({"key": "name_partial", "value": f"{len(matched)}/{len(tokens)}"})
    city = _normalized(str(getattr(lead, "city", ""))).strip()
    if city and city in text:
        score += 12
        evidence.append({"key": "city_match", "value": str(getattr(lead, "city", ""))})
    category = _normalized(str(getattr(lead, "category", ""))).strip()
    if category and any(part in text for part in category.split() if len(part) >= 5):
        score += 5
    return min(90, score), evidence


def _quality_checks(page: PageSnapshot) -> tuple[str, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    secure = urlparse(page.final_url).scheme == "https"
    checks.append({"key": "https", "state": "pass" if secure else "fail"})
    checks.append({"key": "viewport", "state": "pass" if page.has_viewport else "fail"})
    useful_title = 4 <= len(page.title.strip()) <= 160
    checks.append({"key": "title", "state": "pass" if useful_title else "fail"})
    checks.append({"key": "description", "state": "pass" if len(page.description) >= 30 else "warn"})
    checks.append({"key": "schema", "state": "pass" if page.has_schema else "warn"})
    has_contact = bool(page.phone_links or page.whatsapp_links or page.instagram_links)
    checks.append({"key": "contact", "state": "pass" if has_contact else "warn"})
    checks.append({"key": "speed", "state": "pass" if page.elapsed_ms <= 2500 else "warn"})
    hard_failures = sum(1 for item in checks if item["state"] == "fail")
    passes = sum(1 for item in checks if item["state"] == "pass")
    if hard_failures >= 1:
        status = "poor"
    elif passes >= 5:
        status = "good"
    else:
        status = "unknown"
    return status, checks


def _extract_contacts(page: PageSnapshot) -> dict[str, str]:
    from .website_context import public_contacts
    result = {"phone": "", "whatsapp": "", "instagram": ""}
    contacts = public_contacts(page)
    for field in result:
        values = {c['value'] for c in contacts if c['field'] == field}
        if len(values) == 1: result[field] = values.pop()
    return result


AUDIT_PAGE_KEYWORDS = (
    "contato", "contact", "contacto", "fale", "sobre", "about", "empresa",
    "servico", "servicos", "service", "services", "produto", "produtos", "product", "products",
    "agenda", "agendar", "booking", "book", "orcamento", "quote", "presupuesto",
)

CTA_KEYWORDS = (
    "contato", "contact", "contacto", "whatsapp", "orcamento", "quote", "presupuesto",
    "agendar", "agenda", "booking", "book", "comprar", "buy", "pedido", "order",
    "fale", "talk", "message", "ligue", "call", "saiba mais", "learn more",
)


def _same_site(left: str, right: str) -> bool:
    return _display_domain(left) == _display_domain(right)


def _clean_audit_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    path = parsed.path or "/"
    suffix = path.rsplit("/", 1)[-1].lower()
    if "." in suffix and not suffix.endswith((".html", ".htm", ".php", ".asp", ".aspx")):
        return ""
    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query[:250], ""))


def _audit_link_score(url: str, label: str) -> int:
    haystack = _normalized(f"{urlparse(url).path} {label}")
    score = 0
    for keyword in AUDIT_PAGE_KEYWORDS:
        if keyword in haystack:
            score += 5
    if urlparse(url).query:
        score -= 1
    depth = len([part for part in urlparse(url).path.split("/") if part])
    score -= max(0, depth - 2)
    return score


def _audit_internal_urls(home: PageSnapshot, limit: int = 4) -> list[str]:
    candidates: list[tuple[int, str]] = []
    seen: set[str] = {_clean_audit_url(home.final_url)}
    for raw, label in home.links:
        clean = _clean_audit_url(raw)
        if not clean or clean in seen or not _same_site(clean, home.final_url):
            continue
        score = _audit_link_score(clean, label)
        if score <= 0:
            continue
        seen.add(clean)
        candidates.append((score, clean))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [url for _score, url in candidates[: max(0, limit - 1)]]


def _cta_count(page: PageSnapshot) -> int:
    found: set[str] = set()
    for url, label in page.links:
        haystack = _normalized(f"{label} {url}")
        if any(keyword in haystack for keyword in CTA_KEYWORDS):
            found.add(url[:300])
    return len(found)


def _audit_site(pages: list[PageSnapshot]) -> dict[str, Any]:
    if not pages:
        raise ResearchError("Nenhuma página disponível para auditoria.")
    home = pages[0]
    all_phone = any(page.phone_links for page in pages)
    all_whatsapp = any(page.whatsapp_links for page in pages)
    all_email = any(page.email_links for page in pages)
    all_social = any(page.social_links for page in pages)
    forms = sum(page.form_count for page in pages)
    ctas = sum(_cta_count(page) for page in pages)
    total_images = sum(page.image_count for page in pages)
    alt_images = sum(page.image_alt_count for page in pages)
    total_buttons = sum(page.button_count for page in pages)
    labeled_buttons = sum(page.labeled_button_count for page in pages)
    alt_ratio = 1.0 if total_images == 0 else alt_images / total_images
    button_label_ratio = 1.0 if total_buttons == 0 else labeled_buttons / total_buttons
    contact_page = any(_audit_link_score(page.final_url, "") > 0 and any(k in _normalized(page.final_url) for k in ("contato", "contact", "contacto", "fale")) for page in pages[1:])
    max_elapsed = max(page.elapsed_ms for page in pages)
    mixed = sum(page.mixed_content_count for page in pages)
    any_truncated = any(page.truncated for page in pages)
    technologies = list(dict.fromkeys(item for page in pages for item in page.technologies))[:12]
    analytics = list(dict.fromkeys(item for page in pages for item in page.analytics))[:6]
    free_host_domain = bool(home.free_host_domain)
    booking = any(page.booking for page in pages)
    ecommerce = any(page.ecommerce for page in pages)
    catalog_or_menu = any(page.catalog_or_menu for page in pages)
    live_chat = any(page.live_chat for page in pages)

    categories = {
        "technical": {"score": 0, "max": 30},
        "discoverability": {"score": 0, "max": 25},
        "conversion": {"score": 0, "max": 30},
        "accessibility": {"score": 0, "max": 15},
    }
    findings: list[dict[str, Any]] = []

    def add(category: str, points: int) -> None:
        categories[category]["score"] += points

    def finding(key: str, severity: str, label: str, detail: str = "") -> None:
        findings.append({"key": key, "severity": severity, "label": label, "detail": detail})

    secure = urlparse(home.final_url).scheme == "https"
    if secure:
        add("technical", 6)
    else:
        finding("no_https", "high", "Site sem HTTPS")
    if home.has_viewport:
        add("technical", 6)
    else:
        finding("no_viewport", "high", "Viewport responsivo ausente")
    if max_elapsed <= 2500:
        add("technical", 5)
    elif max_elapsed <= 4500:
        add("technical", 2)
        finding("slow_response", "medium", "Resposta lenta", f"Até {max_elapsed} ms")
    else:
        finding("slow_response", "high", "Resposta muito lenta", f"Até {max_elapsed} ms")
    if not any_truncated:
        add("technical", 4)
    else:
        finding("heavy_html", "medium", "HTML muito pesado", "Ao menos uma página excedeu 600 KB de HTML")
    if mixed == 0:
        add("technical", 4)
    else:
        finding("mixed_content", "high", "Conteúdo inseguro em página HTTPS", f"{mixed} recurso(s) HTTP detectado(s)")
    if home.has_canonical:
        add("technical", 3)
    else:
        finding("no_canonical", "low", "URL canônica não encontrada")
    if home.has_favicon:
        add("technical", 2)
    else:
        finding("no_favicon", "low", "Favicon não encontrado")
    if free_host_domain:
        finding("free_host_domain", "medium", "Site usa subdomínio de plataforma", _display_domain(home.final_url))

    useful_title = 4 <= len(home.title.strip()) <= 160
    if useful_title:
        add("discoverability", 6)
    else:
        finding("weak_title", "medium", "Título da página ausente ou inadequado")
    if len(home.description.strip()) >= 30:
        add("discoverability", 5)
    else:
        finding("no_description", "medium", "Meta description fraca ou ausente")
    if home.has_schema:
        add("discoverability", 6)
    else:
        finding("no_schema", "medium", "Dados estruturados não encontrados")
    if home.h1_count == 1:
        add("discoverability", 4)
    elif home.h1_count == 0:
        finding("no_h1", "medium", "H1 principal não encontrado")
    else:
        add("discoverability", 2)
        finding("multiple_h1", "low", "Mais de um H1 encontrado", str(home.h1_count))
    if home.html_lang:
        add("discoverability", 2)
    else:
        finding("no_lang", "low", "Idioma da página não declarado")

    if all_phone:
        add("conversion", 4)
    else:
        finding("no_phone", "medium", "Telefone não encontrado no site")
    if all_whatsapp:
        add("conversion", 5)
    else:
        finding("no_whatsapp", "medium", "WhatsApp não encontrado no site")
    if all_email:
        add("conversion", 4)
    else:
        finding("no_email", "low", "E-mail não encontrado no site")
    if forms:
        add("conversion", 5)
    else:
        finding("no_form", "medium", "Formulário de contato não encontrado")
    if ctas >= 2:
        add("conversion", 5)
    elif ctas == 1:
        add("conversion", 2)
        finding("few_ctas", "medium", "Poucas ações comerciais claras")
    else:
        finding("no_cta", "high", "Nenhuma ação comercial clara detectada")
    if contact_page:
        add("conversion", 4)
    else:
        finding("no_contact_page", "medium", "Página de contato não encontrada")
    if all_social:
        add("conversion", 3)
    else:
        finding("no_social", "low", "Redes sociais não vinculadas no site")

    if home.html_lang:
        add("accessibility", 3)
    if alt_ratio >= 0.8:
        add("accessibility", 6)
    elif alt_ratio >= 0.5:
        add("accessibility", 3)
        finding("image_alt_partial", "medium", "Textos alternativos incompletos", f"{round(alt_ratio * 100)}% das imagens")
    else:
        finding("image_alt_low", "high", "Poucas imagens têm texto alternativo", f"{round(alt_ratio * 100)}% das imagens")
    if button_label_ratio >= 0.9:
        add("accessibility", 4)
    elif button_label_ratio >= 0.6:
        add("accessibility", 2)
        finding("button_labels_partial", "medium", "Alguns botões podem não ter rótulo claro")
    else:
        finding("button_labels_low", "high", "Botões sem rótulo claro detectados")
    if home.h1_count >= 1:
        add("accessibility", 2)

    quality_score = sum(int(item["score"]) for item in categories.values())
    critical = {item["key"] for item in findings if item["severity"] == "high"}
    if quality_score >= 82 and not critical:
        website_status = "good"
    elif quality_score < 65 or {"no_https", "no_viewport", "no_cta"}.intersection(critical):
        website_status = "poor"
    else:
        website_status = "unknown"

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["key"]))
    finding_keys = {item["key"] for item in findings}
    angle_rules = [
        ("conversion", "Conversão e contato", {"no_cta", "few_ctas", "no_form", "no_whatsapp", "no_phone"}),
        ("responsive", "Experiência mobile e acessibilidade", {"no_viewport", "image_alt_low", "image_alt_partial", "button_labels_low", "button_labels_partial"}),
        ("discoverability", "SEO e descoberta local", {"weak_title", "no_description", "no_schema", "no_h1", "no_lang"}),
        ("performance", "Performance e confiança técnica", {"slow_response", "heavy_html", "mixed_content", "no_https"}),
        ("presence", "Presença e credibilidade", {"no_contact_page", "no_social", "no_favicon", "no_canonical", "free_host_domain"}),
    ]
    angles = [
        {"key": key, "label": label, "evidence": sorted(finding_keys.intersection(keys))}
        for key, label, keys in angle_rules
        if finding_keys.intersection(keys)
    ]
    return {
        "level": "deep",
        "quality_score": quality_score,
        "website_status": website_status,
        "pages_checked": len(pages),
        "categories": categories,
        "findings": findings[:16],
        "angles": angles[:5],
        "pages": [
            {
                "url": page.final_url[:500],
                "title": page.title[:220],
                "elapsed_ms": page.elapsed_ms,
                "body_bytes": page.body_bytes,
            }
            for page in pages
        ],
        "signals": {
            "phone": all_phone,
            "whatsapp": all_whatsapp,
            "email": all_email,
            "social": all_social,
            "forms": forms,
            "ctas": ctas,
            "contact_page": contact_page,
            "image_alt_ratio": round(alt_ratio, 3),
            "button_label_ratio": round(button_label_ratio, 3),
            "mixed_content": mixed,
            "generator": home.generator,
            "own_domain": not free_host_domain,
            "free_host_domain": free_host_domain,
            "technologies": technologies,
            "analytics": analytics,
            "booking": booking,
            "ecommerce": ecommerce,
            "catalog_or_menu": catalog_or_menu,
            "live_chat": live_chat,
        },
    }


class BraveSearchClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SCOUT_BRAVE_SEARCH_API_KEY", "").strip()
        self.base_url = "https://api.search.brave.com/res/v1/web/search"
        self.timeout = max(3.0, min(float(os.getenv("SCOUT_WEB_SEARCH_TIMEOUT", "7")), 12.0))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, lead: Any, locale: str) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        return self._search(lead, locale)

    @metered('brave')
    def _search(self, lead: Any, locale: str) -> list[dict[str, str]]:
        if not self.api_key:
            return []
        lang = (locale or "en").split("-", 1)[0].lower()
        country = (str(getattr(lead, "country", "")) or "US").upper()
        name = str(getattr(lead, "name", "")).strip()
        city = str(getattr(lead, "city", "")).strip()
        category = str(getattr(lead, "category", "")).strip()
        qualifier = "site oficial" if lang == "pt" else "sitio oficial" if lang == "es" else "official website"
        query = f'"{name}" {city} {category} {qualifier}'.strip()
        params = urlencode({"q": query[:500], "count": 10, "country": country, "search_lang": lang})
        request = Request(
            f"{self.base_url}?{params}",
            headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
            method="GET",
        )
        try:
            with build_opener().open(request, timeout=self.timeout) as response:
                payload = response.read(1_000_000)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise SearchConfigurationError("A chave do mecanismo de pesquisa foi recusada.") from exc
            raise ResearchError("A pesquisa web recusou a consulta.") from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise ResearchError("A pesquisa web demorou para responder.") from exc
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ResearchError("A pesquisa web retornou resposta inválida.") from exc
        raw = data.get("web", {}).get("results", []) if isinstance(data, dict) else []
        results: list[dict[str, str]] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            host = _host(url)
            if not host or _blocked_host(host):
                continue
            results.append({
                "url": url[:1000],
                "title": str(item.get("title") or "")[:300],
                "description": str(item.get("description") or "")[:1000],
            })
        return results[:10]


class WebsiteResearcher:
    def __init__(self) -> None:
        self.search_client = BraveSearchClient()
        self.timeout = max(2.5, min(float(os.getenv("SCOUT_WEBSITE_TIMEOUT", "5")), 10.0))
        self.workers = max(1, min(int(os.getenv("SCOUT_WEBSITE_WORKERS", "4")), 6))
        self.user_agent = os.getenv("RADAR_USER_AGENT", f"ScoutLIQ/1.0 (+{ORIGIN})")[:250]
        self.confirm_threshold = max(50, min(int(os.getenv("SCOUT_WEBSITE_CONFIRM_THRESHOLD", "62")), 90))

    @property
    def search_configured(self) -> bool:
        return self.search_client.configured

    def _candidate_urls(self, lead: Any, locale: str) -> tuple[list[tuple[str, str]], list[dict[str, str]]]:
        candidates: list[tuple[str, str]] = []
        known = str(getattr(lead, "website", "") or "").strip()
        if known:
            candidates.append((known, "known"))
        for url in candidate_domains(str(getattr(lead, "name", "")), str(getattr(lead, "country", ""))):
            candidates.append((url, "direct"))
        search_results: list[dict[str, str]] = []
        if self.search_client.configured:
            search_results = self.search_client.search(lead, locale)
            for item in search_results:
                candidates.append((item["url"], "search"))
        unique: list[tuple[str, str]] = []
        seen: set[str] = set()
        for url, source in candidates:
            host = _display_domain(url)
            if not host or _blocked_host(host) or host in seen:
                continue
            seen.add(host)
            unique.append((url, source))
        return unique[:12], search_results

    def research(self, lead: Any, locale: str = "pt-BR") -> dict[str, Any]:
        candidates, search_results = self._candidate_urls(lead, locale)
        snapshots: list[tuple[PageSnapshot, str]] = []
        errors = 0
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futures = {
                submit(pool, _fetch_page, url, timeout=self.timeout, user_agent=self.user_agent): (url, source)
                for url, source in candidates
            }
            for future in as_completed(futures):
                _url, source = futures[future]
                try:
                    snapshots.append((future.result(), source))
                except ResearchError:
                    errors += 1

        ranked: list[tuple[int, PageSnapshot, str, list[dict[str, Any]]]] = []
        for page, source in snapshots:
            confidence, evidence = _identity_score(lead, page, search_hint=source == "search")
            ranked.append((confidence, page, source, evidence))
        ranked.sort(key=lambda item: (item[0], item[2] == "known"), reverse=True)

        checked_at = int(time.time())
        sources = [
            {"url": item["url"], "title": item["title"], "kind": "search"}
            for item in search_results[:6]
        ]
        if not ranked or ranked[0][0] < self.confirm_threshold:
            best_search: tuple[int, dict[str, str], list[dict[str, Any]]] | None = None
            for item in search_results:
                search_score, search_evidence = _search_result_score(lead, item)
                if best_search is None or search_score > best_search[0]:
                    best_search = (search_score, item, search_evidence)
            best_ranked_score = ranked[0][0] if ranked else 0
            best_ranked_evidence = ranked[0][3] if ranked else []
            candidate_url = ""
            candidate_score = best_ranked_score
            candidate_evidence = best_ranked_evidence
            if best_search and best_search[0] > candidate_score:
                candidate_score = best_search[0]
                candidate_url = best_search[1]["url"][:500]
                candidate_evidence = best_search[2]
            return {
                "status": "unverified" if (ranked or best_search) else "not_found",
                "provider": "brave+direct" if self.search_client.configured else "direct",
                "website_url": candidate_url,
                "website_status": "unknown",
                "confidence": candidate_score,
                "checked_at": checked_at,
                "evidence": candidate_evidence,
                "checks": [],
                "sources": sources,
                "contacts": {},
                "search_configured": self.search_client.configured,
                "candidates_checked": len(candidates),
                "fetch_errors": errors,
            }

        confidence, page, source, evidence = ranked[0]
        from .website_context import inspect
        context = inspect([page])
        website_status, checks = _quality_checks(page)
        sources.insert(0, {"url": page.final_url, "title": page.title, "kind": source})
        return {
            "status": "confirmed",
            "provider": "brave+direct" if self.search_client.configured else "direct",
            "website_url": page.final_url[:500],
            "website_status": website_status,
            "confidence": confidence,
            "checked_at": checked_at,
            "evidence": evidence,
            "checks": checks,
            "sources": sources[:8],
            "contacts": _extract_contacts(page),
            "context": context,
            "search_configured": self.search_client.configured,
            "candidates_checked": len(candidates),
            "fetch_errors": errors,
            "page": {
                "title": page.title[:300],
                "description": page.description[:600],
                "lang": page.html_lang,
                "elapsed_ms": page.elapsed_ms,
                "body_bytes": page.body_bytes,
                "domain": _display_domain(page.final_url),
                "own_domain": not page.free_host_domain,
                "free_host_domain": page.free_host_domain,
                "technologies": page.technologies,
                "analytics": page.analytics,
                "booking": page.booking,
                "ecommerce": page.ecommerce,
                "catalog_or_menu": page.catalog_or_menu,
                "live_chat": page.live_chat,
                "email": bool(page.email_links),
                "forms": page.form_count,
                "social": bool(page.social_links),
                "whatsapp_site": bool(page.whatsapp_links),
                "mixed_content": page.mixed_content_count,
            },
        }

# Deep audit is attached after the class definition to keep the first-layer researcher compact.
def _website_researcher_deep_audit(self: WebsiteResearcher, lead: Any, website_url: str) -> dict[str, Any]:
    target = (website_url or "").strip()
    if not target:
        raise ResearchError("Site não confirmado para auditoria.")
    home = _fetch_page(target, timeout=self.timeout, user_agent=self.user_agent)
    urls = _audit_internal_urls(home, limit=4)
    pages = [home]
    errors = 0
    if urls:
        with ThreadPoolExecutor(max_workers=min(self.workers, 3)) as pool:
            futures = [submit(pool, _fetch_page, url, timeout=self.timeout, user_agent=self.user_agent) for url in urls]
            for future in as_completed(futures):
                try:
                    page = future.result()
                    if _same_site(page.final_url, home.final_url):
                        pages.append(page)
                except ResearchError:
                    errors += 1
    audit = _audit_site(pages)
    from .website_context import inspect
    audit['context'] = inspect(pages)
    audit["audited_at"] = int(time.time())
    audit["fetch_errors"] = errors
    return audit

WebsiteResearcher.deep_audit = _website_researcher_deep_audit
