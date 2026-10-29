"""Explicit capabilities and finite pages for existing configured sources.

Extensions implement capabilities(sector) and search_page(query, offset, limit),
returning normalized DiscoveryBatch. No new source or credential is selected here.
"""
from copy import copy
from .providers import DiscoveryBatch, _selectors, _geoapify_categories, GeoapifyProvider, OpenStreetMapProvider, ProviderConfigurationError

QUERIES = {'odontologia': 'dentista', 'clinica': 'clínica', 'salao': 'salão', 'veterinaria': 'veterinário', 'contabilidade': 'contador', 'advocacia': 'advogado', 'imobiliaria': 'imobiliária'}

def capabilities(provider, sector, location=None, area=None):
    if area:
        base = capabilities(provider, sector)
        if isinstance(provider, (GeoapifyProvider, OpenStreetMapProvider)):
            return {**base, 'coverage': 'Área exata do mapa; categorias comerciais da fonte, coleta limitada e recorte antes de persistir.' if not sector else 'Área desenhada preservada; coleta limitada no círculo de cobertura e recorte exato antes de persistir.'}
        if hasattr(provider, 'area_capabilities'):
            declared = provider.area_capabilities(area)
            return {**base, **declared, 'supported': bool(base['supported'] and declared.get('supported'))}
        return {'supported':False, 'pagination':False, 'coverage':'Área não suportada',
                'reason':'A fonte não confirma a geografia das empresas nesta área. Nenhum município ou país foi presumido.'}
    if location:
        if isinstance(provider, GeoapifyProvider) and location.source == 'geoapify' and location.latitude is not None:
            base = capabilities(provider, sector)
            return {**base, 'coverage': 'Limite administrativo selecionado; categorias comerciais da Geoapify, coleta ampla limitada.' if not sector else 'Limite administrativo selecionado; coleta limitada por páginas, orçamento e prazo.'}
        if hasattr(provider, 'location_capabilities'):
            base=capabilities(provider,sector); declared=provider.location_capabilities(location)
            return {**base, **declared, 'supported':bool(base['supported'] and declared.get('supported'))}
        return {'supported': False, 'pagination': False, 'coverage': 'Território não suportado',
                'reason': 'A fonte configurada não cobre este limite administrativo. Nenhum raio foi aplicado.'}
    if not sector and hasattr(provider, 'general_capabilities'): return provider.general_capabilities()
    if not sector and not isinstance(provider, (GeoapifyProvider, OpenStreetMapProvider)):
        return {'supported':False,'pagination':False,'coverage':'Exploração geral indisponível','reason':'A fonte não declara suporte à exploração geral.'}
    if hasattr(provider, 'capabilities'): return provider.capabilities(sector)
    query = QUERIES.get(sector, sector)
    if isinstance(provider, GeoapifyProvider):
        supported = not sector or bool(_geoapify_categories(query))
        return {'supported': supported, 'pagination': True, 'coverage': 'Categorias comerciais suportadas pela Geoapify; coleta ampla limitada, não um censo.' if not sector else 'Região administrativa quando disponível; caso contrário, raio de 5 km.', 'reason': '' if supported else 'Setor sem correspondência específica no adaptador Geoapify; nenhuma categoria genérica será usada.'}
    if isinstance(provider, OpenStreetMapProvider):
        supported = not sector or bool(_selectors(query)) or sector=='tecnologia'
        return {'supported': supported, 'pagination': False, 'coverage': 'Tags comerciais suportadas no OpenStreetMap; uma coleta sem paginação, cobertura parcial.' if not sector else 'Raio de 5 km; uma coleta limitada por setor, sem cobertura nacional.', 'reason': '' if supported else 'Setor sem seletor específico no adaptador OpenStreetMap.'}
    return {'supported': False, 'pagination': False, 'coverage': 'Indisponível', 'reason': 'Fonte não configurada para busca inteligente.'}

def legacy_capabilities(provider, query):
    supported=provider is not None and callable(getattr(provider,'search',None))
    return {'supported':supported,'pagination':False,
            'coverage':'Consulta histórica preservada; uma coleta limitada pela configuração da fonte.',
            'reason':'' if supported else 'Fonte de descoberta indisponível.'}


def search_page(provider, query, offset, limit, *, compatible=False):
    limit = max(1, min(100, limit))
    if compatible:
        if not legacy_capabilities(provider,query)['supported']:
            raise ProviderConfigurationError('Fonte de descoberta indisponível.')
        if offset: return DiscoveryBatch(provider=provider.name,location_label=query.location,results=[],complete=True)
        return provider.search(query)
    if not query.category and not capabilities(provider,'')['supported']:
        raise ProviderConfigurationError('A fonte não declara suporte à exploração geral.')
    if query.resolved_location and not capabilities(provider, query.category, query.resolved_location)['supported']:
        raise ProviderConfigurationError('Território ou setor não suportado pela fonte configurada.')
    if hasattr(provider, 'search_page'):
        return provider.search_page(query, offset, limit)
    source = copy(provider)  # Never mutate the shared HTTP provider instance.
    if isinstance(source, GeoapifyProvider):
        source._smart_offset = offset
        source.region_page_size = source.region_max_results = source.region_scan_limit = limit
        source.candidate_limit = source.max_results = limit
        source.enrich_limit = 0  # ResearchBatch owns progressive investigation.
    elif isinstance(source, OpenStreetMapProvider):
        if offset: return DiscoveryBatch(provider=source.name, location_label=query.location, results=[], complete=True)
        source.max_results = limit
        source.overpass_urls = source.overpass_urls[:1]  # One bounded Overpass attempt per executor reservation.
        if query.category=='tecnologia':
            # Official OSM tag office=it; B2B coverage remains sparse.
            source._overpass_query = lambda q, lat, lon: f'[out:json][timeout:10];nwr(around:5000,{lat:.6f},{lon:.6f})["name"]["office"="it"];out tags center qt {limit};'
            # Avoid the legacy unknown-category name filter: selector already exact.
            query = query.model_copy(update={'category': ''})
    else:
        raise ProviderConfigurationError('Fonte sem contrato de busca inteligente.')
    return source.search(query)
