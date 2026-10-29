"""Bounded, editable commercial intent; deliberately not an unrestricted NLP claim."""
import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .commercial_fit import norm
from .search_location import SearchLocation, SearchArea
from .discovery_contract import LegacySearch

# Canonical names also serve as provider queries. Unsupported sectors stay explicit.
SECTORS = {
    'hamburgueria': ('hamburguer', 'hamburgues', 'burger'),
    'odontologia': ('odontolog', 'dentist'), 'restaurante': ('restaurante', 'restaurant'),
    'cafeteria': ('cafeteria', 'coffee', 'cafe'), 'barbearia': ('barbearia', 'barber'),
    'clinica': ('clinica', 'clinic'), 'salao': ('salao', 'hairdresser'),
    'academia': ('academia', 'fitness', 'gym'), 'pet shop': ('pet shop', 'petshop'),
    'veterinaria': ('veterinar',), 'oficina': ('oficina', 'car repair'),
    'hotel': ('hotel', 'pousada'), 'contabilidade': ('contabil', 'accountant'),
    'advocacia': ('advoca', 'lawyer'), 'imobiliaria': ('imobiliari', 'real estate'),
    'padaria': ('padaria', 'bakery'), 'farmacia': ('farmacia', 'pharmacy'),
    'tecnologia': ('tecnologia', 'software', 'technology', 'tech companies', 'office it'),
    'consultoria': ('consultoria', 'consulting'), 'industria': ('industria', 'manufactur'),
}
Requirement = Literal['no_site', 'poor_site', 'whatsapp', 'phone', 'instagram', 'active', 'independent']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Market(Strict):
    country: str = Field(default='', pattern=r'^([A-Z]{2})?$')
    region: str = Field(default='', max_length=100)
    city: str = Field(default='', max_length=100)

class Profile(Strict):
    business_type: Literal['local', 'b2b', 'any'] = 'local'
    size: Literal['small_medium', 'any'] = 'small_medium'
    independence: Literal['preferred', 'required', 'any'] = 'preferred'

class Intent(Strict):
    query: str = Field(default="", max_length=1200)
    search_mode: Literal["general", "directed", "filtered", "ambiguous", "legacy"] = "ambiguous"
    market: Market = Field(default_factory=Market)
    location: SearchLocation | None = None
    area: SearchArea | None = None
    legacy: LegacySearch | None = None
    sectors: list[str] = Field(default_factory=list, max_length=4)
    profile: Profile = Field(default_factory=Profile)
    requirements: list[Requirement] = Field(default_factory=list, max_length=7)
    preferences: list[Requirement] = Field(default_factory=list, max_length=7)
    exclusions: list[str] = Field(default_factory=lambda: ['centralized_chains', 'public_entities', 'closed'], max_length=12)
    target: Literal[25, 50, 75, 100] = 50
    unresolved: list[str] = Field(default_factory=list, max_length=15)
    requirement_mode: Literal['all', 'any'] = 'all'

    @model_validator(mode='before')
    @classmethod
    def historical_mode(cls, values):
        if isinstance(values, dict) and 'search_mode' not in values:
            values = dict(values)
            values['search_mode'] = ('legacy' if values.get('legacy') else 'directed' if values.get('sectors')
                                     else 'general' if not str(values.get('query', '')).strip() else 'ambiguous')
        return values

    @model_validator(mode='after')
    def single_geography(self):
        if self.legacy and (self.location or self.area):
            raise ValueError('Consulta histórica não pode combinar outra geografia')
        if self.location and self.area:
            raise ValueError('Selecione uma área ou uma localização administrativa')
        return self

class InterpretInput(Strict):
    text: str = Field(default="", max_length=1200)
    target: Literal[25, 50, 75, 100] = 50
    mode: Literal['deterministic', 'semantic'] = 'deterministic'
    request_key: UUID | None = None

GEOGRAPHIC_MESSAGES = {
    'city': 'Informe uma cidade: as fontes configuradas não cobrem um país inteiro nesta busca.',
    'country': 'Confirme o país no resumo antes de executar.',
    'semantic_city': 'Informe uma cidade antes de executar.',
    'semantic_country': 'Confirme o país antes de executar.',
    'inferred_country': 'País inferido pelo modelo; confirme o país no resumo antes de executar.',
}


def interpret(text, target=50):
    value = norm(text)
    intent = Intent(query=text, target=target)
    # Extract market before filters, never interpret a whole sentence as a city.
    match = None
    for prefix in re.finditer(r'\b(?:em|in|en)\s+', value):
        # "Especializadas em burgers" describes a sector, not a city.
        # A later "em Recife" remains eligible as an explicit location.
        if re.search(r'\b(?:especializad[oa]s?|especialistas?|specialized|specialising|specializing)\s+$', value[:prefix.start()]):
            continue
        match = re.match(r'(.+?)(?=\s+(?:sem|com|without|with|exceto|excluindo|preferencialmente|que|mas|nao)\b|$)', value[prefix.end():])
        if match:
            break
    if match:
        location = match.group(1).strip(' .,')
        for words, code in [('estados unidos', 'US'), ('united states', 'US'), ('eua', 'US'), ('usa', 'US'), ('brasil', 'BR'), ('brazil', 'BR'), ('portugal', 'PT')]:
            if words in location:
                intent.market.country = code
                location = location.replace(words, '').strip(' ,')
        parts = [x.strip() for x in location.split(',') if x.strip()]
        if parts: intent.market.city = parts[0][:100]
        if len(parts)>1: intent.market.region = parts[1][:100]
    if not intent.market.city:
        intent.unresolved.append(GEOGRAPHIC_MESSAGES['city'])
    if not intent.market.country:
        intent.unresolved.append(GEOGRAPHIC_MESSAGES['country'])
    if re.search(r'\b(nao|not)\b', value):
        intent.unresolved.append('Há uma negação no pedido. Confira os requisitos e exclusões; negações livres não são aplicadas automaticamente.')
    # Exclusion clauses are removed before positive sector detection.
    excluded = []
    def exclude(match):
        excluded.append(match.group(1)); return ' '
    positive = re.sub(r'\b(?:exceto|excluindo|nao quero|nao incluir|sem incluir|excluding)\s+([^,;.]+)', exclude, value)
    for sector, aliases in SECTORS.items():
        if any(alias in positive for alias in aliases): intent.sectors.append(sector)
        if any(any(alias in clause for alias in aliases) for clause in excluded): intent.exclusions.append(sector)
    # Specific dentistry must not accidentally become a generic clinic search.
    if 'odontologia' in intent.sectors and 'clinica' in intent.sectors: intent.sectors.remove('clinica')
    if 'hamburgueria' in intent.sectors and 'restaurante' in intent.sectors: intent.sectors.remove('restaurante')
    intent.sectors = intent.sectors[:4]
    if value and not intent.sectors: intent.unresolved.append('Setor não reconhecido; selecione ou descreva um setor suportado.')
    terms = {'no_site': r'\b(sem site|sem website|no website|without website)\b',
             'poor_site': r'\b(site ruim|site fraco|site desatualizado|poor website)\b',
             'whatsapp': r'\b(com whatsapp|with whatsapp)\b', 'phone': r'\b(com telefone|with phone)\b',
             'instagram': r'\b(com instagram|with instagram)\b', 'active': r'\b(ativ[oa]s?|active)\b',
             'independent': r'\b(independentes?|independent)\b'}
    for key, pattern in terms.items():
        found = re.search(pattern, positive)
        if found:
            preceding = positive[max(0, found.start()-35):found.start()]
            if re.search(r'(nao|not)\s+(?:quero\s+)?$', preceding):
                intent.unresolved.append(f'Negação de {found.group(0)} exige correção explícita no resumo.')
            elif re.search(r'(preferencia|preferencialmente|de preferencia|preferably)\s*$', preceding): intent.preferences.append(key)
            else: intent.requirements.append(key)
    if re.search(r'\b(ou|or)\b', positive) and len(intent.requirements)>1:
        intent.unresolved.append('Combinação com OU: confirme se os requisitos são todos obrigatórios ou alternativos.')
    if 'independent' in intent.requirements: intent.profile.independence = 'required'
    if re.search(r'\b(b2b|software|tecnologia|technology)\b', value): intent.profile.business_type = 'b2b'
    if re.search(r'\b(menos de|mais de|avaliacoes|reviews|faturamento|funcionarios|receita|nota|rating)\b', value):
        intent.unresolved.append('Limites numéricos ou porte não foram convertidos em filtro; ajuste o pedido antes de executar.')
    intent.search_mode = 'general' if not value else 'ambiguous' if not intent.sectors else 'directed'
    return intent

def discovery_sectors(intent):
    # One broad source query, with category unspecified; never synthetic niches.
    return intent.sectors or ['']

def requirements(lead, intent):
    from .commercial_fit import facts
    data = facts(lead)
    site = getattr(lead, 'website_status', 'unknown')
    checks = {'no_site': True if site=='none' and not lead.website else False if lead.website and site in ('good','poor') else None,
              'poor_site': True if site=='poor' else False if site in ('none','good') else None,
              'whatsapp': True if lead.whatsapp else None, 'phone': True if lead.phone else None,
              'instagram': True if lead.instagram else None,
              'active': True if lead.instagram_active or data.get('operating_status')=='active' else False if data.get('operating_status')=='closed' else None,
              'independent': True if data.get('independence')=='independent' else False if data.get('independence')=='centralized' else None}
    selected = [checks[key] for key in intent.requirements]
    if not selected: return 'met'
    if intent.requirement_mode=='any': return 'met' if True in selected else 'unknown' if None in selected else 'unmet'
    return 'unmet' if False in selected else 'unknown' if None in selected else 'met'
