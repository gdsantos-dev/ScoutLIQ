# Contrato de localização — v1.37

A descrição comercial e o território são entradas separadas. A seleção envia ID + consulta + país opcional. O backend resolve novamente o ID no catálogo (ou em cache validado); nomes e coordenadas enviados pelo navegador não viram fatos autorizados.

SearchLocation contém identificador, nome, nome formatado, tipo district/city/county/state/country, subdivisão, cidade, estado, código regional, país, código do país, fonte e resolved_at. Coordenadas e bbox são opcionais e só vêm da fonte. Bbox é envelope; não se apresenta como polígono administrativo. Nenhum homônimo é escolhido automaticamente.

Geoapify fornece o autocomplete administrativo configurado. IBGE fornece fallback de municípios brasileiros, sem fabricar coordenadas, bairros ou limites. Sem capacidade de descoberta do provedor para um território, a busca informa a limitação; estado/país não vira raio silenciosamente. Selecionar cidade/estado não garante cobertura completa nem atingir a meta.

SearchArea usa bounds ou polygon: números finitos, envelope ordenado, até 25 km de raio derivado, 3–32 vértices distintos no polígono, sem cruzamentos e com área não nula. O mapa restringe a mesma busca. Cidade e país dos resultados precisam ser observados; não são inferidos do centro do mapa.

## Custo e persistência

- Autocomplete: debounce de 350 ms e limite HTTP de 30/minuto por usuário.
- Geoapify: reservas duráveis antes da consulta; padrões de 300 chamadas/dia na instalação e 100/usuário, configuráveis por RADAR_LOCATION_DAILY_CALLS e RADAR_LOCATION_USER_DAILY_CALLS. Zero impede consultas sem cache.
- Cache por usuário, consulta, país, idioma, modo e configuração do provedor: padrão de 1 hora, configurável de 60 s a 24 h. Expirados são removidos na próxima consulta.
- Gate transacional serializa a reserva entre processos; erros e interrupções não devolvem uma chamada possivelmente cobrada. Cache hit não consome outra reserva. Não há preço monetário inferido.
- O ledger existente registra kind=location e provider=geoapify-location. Consulta e credencial não são escritas no ledger. A chave do cache é um hash; resultados administrativos são isolados por usuário.
- Sem chave Geoapify, permanece o cache IBGE gratuito de 24 h. Não se usa Nominatim público para autocomplete.

Cache permitido pela documentação pública da Geoapify, consultada em 22/10/2026: https://www.geoapify.com/ . A interface inclui atribuição Geoapify/OpenStreetMap quando exibe dados dessa fonte. A instalação deve respeitar seu plano e os termos vigentes.

Testado localmente: schema, seleção por ID, conflitos, limites/cache, falhas, isolamento e migração. Não homologado: catálogo e cobertura internacionais com credenciais reais, precisão dos limites, tarifas ou qualidade dos estabelecimentos.
