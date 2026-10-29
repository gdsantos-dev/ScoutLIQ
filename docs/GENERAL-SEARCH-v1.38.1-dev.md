# Busca Unificada — v1.38.1-dev

## Experiência

No Radar e nas oportunidades, Buscar empresas mantém o mesmo formulário. O que buscar é opcional; a localização continua exigindo seleção validada no catálogo ou uma área existente do mapa. Quantidade aceita 25, 50, 75 ou 100 oportunidades qualificadas, não apenas empresas coletadas.

Pedido vazio inicia exploração geral. Hamburguerias continua direcionando ao setor reconhecido. Ajustar critérios permite zero a quatro nichos, requisitos, preferências e exclusões. Texto não reconhecido não vira busca geral: exige correção ou aceite explícito dos critérios revisados. Histórico e buscas salvas identificam Exploração geral. Reabrir preserva localização, filtros e meta.

## Contrato e auditoria

A auditoria da base integrada encontrou mínimos de texto/setores no frontend e nos schemas, indexação direta de sectors em query_for/save, planejamento por setor e validação de rotinas que assumiam uma lista não vazia. Foram alterados os consumidores necessários, preservando descoberta, CRM e executor compartilhados.

Intent.search_mode distingue general, directed, filtered, ambiguous e legacy. Consulta vazia não recebe o setor artificial empresas. Payloads antigos sem modo inferem legacy quando contêm LegacySearch, directed quando têm setores, general quando query está vazia e ambiguous nos demais casos. Os campos existentes são mantidos; não é necessária nova migração. Jobs persistidos mantêm seus cursores, leases e orçamento; o planejamento histórico sem plan conserva o caminho antigo.

Uma lista vazia usa internamente uma única etapa de descoberta com categoria vazia. Isso não é um nicho oculto. Critérios avançados definem filtered, podendo restringir setores ou apenas requisitos/exclusões. O interpretador semântico não controla o modo de execução; busca vazia não aciona o modelo, mesmo com política automática habilitada. Modelo e orçamento permanecem opcionais nos contratos anteriores.

## Fontes e geografia

| Fonte | Exploração geral | Limites e geografia |
| --- | --- | --- |
| Geoapify | Lista comercial ampla já existente em GEOAPIFY_DEFAULT_CATEGORIES, em uma chamada Places por página | Limite administrativo selecionado exige referência Geoapify válida; não há conversão silenciosa de IBGE em raio. Área do mapa usa círculo de cobertura e recorte exato antes de persistir. Até 100 candidatos/página; offsets e tetos existentes. |
| OpenStreetMap | União existente de DEFAULT_DISCOVERY_SELECTORS em uma consulta Overpass | Área explícita do mapa; até 100 resultados, sem paginação. Exige cidade/município e país ISO2 observados nas tags; sem esses dados, o item não entra. Não declara suporte a limite administrativo do catálogo. Um endpoint Overpass por reserva, sem fallback automático. |
| Adaptador adicional | Somente com general_capabilities explícito e compatibilidade geográfica | location_capabilities/area_capabilities não podem tornar verdadeira uma capacidade geral ausente. |

Não é um censo de todos os negócios da cidade. OSM pode retornar poucos resultados pela ausência de endereço estruturado. Geoapify/OSM são verificados com respostas controladas; não há alegação de homologação externa nesta entrega. Nenhuma nova API paga é obrigatória, e nenhuma fonte é selecionada automaticamente.

## Distribuição e qualificação

A exploração geral coleta uma segunda página quando a fonte permite e ainda há orçamento/prazo, antes de encerrar pela meta da primeira página. Essa amostragem reduz viés inicial, mas não garante diversidade se o provedor retornar apenas um setor.

A investigação alterna categorias observadas dentro de faixas de dez pontos do score canônico e do mesmo nível de preferência. Empresas descartadas não participam. O histórico de categorias já investigadas orienta a próxima alocação. A lista final alterna categorias apenas em empates exatos de score e preferências: uma oportunidade mais fraca não desloca uma mais forte por cota. Não existe bônus, score paralelo nem alteração automática de pesos.

São preservados 12 chamadas de coleta, 600 candidatos, 200 investigações e o prazo existente. A reserva de trabalho, auditoria, interrupção, retomada e deduplicação continuam no worker. Falta de cobertura/orçamento produz resultado parcial; empresas já encontradas ficam disponíveis. Dados desconhecidos permanecem desconhecidos.

## Módulos alterados

- search_intent.py: modo explícito, compatibilidade e texto opcional.
- smart_search.py: critérios zero a quatro nichos, validação, etapa ampla, salvamento e seleção limitada.
- discovery_plan.py: rótulo geral e distribuição por qualidade/categoria.
- search_sources.py e providers.py: capacidades reais, coleta ampla existente e geografia observada no OSM.
- semantic_intent.py: execução geral não delegada ao modelo.
- routines.py: validação e seleção compatíveis com setores vazios.
- UnifiedSearch, SearchCriteria, searchTypes, Radar e traduções: adaptação do mesmo fluxo, histórico/salvos e PT/EN/ES.
- Metadados de versão, testes, fixture e scripts de validação/empacotamento.

Absorção, migração 028, Score 3.0, CommercialFit, research_worker, main, App e Pipeline permanecem byte a byte iguais à base integrada. search_compat/discovery_contract foram auditados e reutilizados sem modificação.

## Próximo desenvolvimento

Homologar amostras pequenas autorizadas nos provedores configurados e revisar manualmente oportunidades por cidade/setor. Medir precisão, descarte, concentração e resultado comercial separadamente das contagens técnicas. Reusar os casos revisados e aprendizado supervisionado existentes, sem recalibrar pesos automaticamente. Melhorias de cobertura OSM exigem evidências geográficas compatíveis; não presumir cidade/país para elevar números.


## Segurança e custo do ciclo

Os schemas continuam extra=forbid, com limites de tamanho/listas e campos permitidos. Início, controle e salvamento reutilizam autenticação, CSRF, limite de frequência e autorização por usuário. Não se aceitam owner_id, user_id ou parâmetros de SQL. Exclusões/nichos são conferidos contra o contrato; saída textual continua escapada pelo React. Não foram adicionados endpoints administrativos, uploads, SQL textual, NoSQL, execução dinâmica, comandos de sistema ou URLs de destino no frontend.

Coletores continuam em endpoints configurados; dados recebidos passam pelo LeadInput e pelo recorte geográfico antes de gravar. A fonte autorizada permanece vinculada ao job, e fontes sem capacidade declarada produzem resultado parcial. Reservas, leases, cancelamento e limites são os existentes. Credenciais ficam no backend. Não há novas dependências de runtime; o lock frontend só muda a versão do produto. Não foi feita nova consulta externa de vulnerabilidades neste ciclo; homologação e revisão antes de deploy continuam necessárias.

A distribuição mantém referências aos Leads e calcula prioridades uma vez por etapa, evitando consultas ORM repetidas a cada comparação entre categorias. A otimização não guarda caches entre usuários ou entre etapas; revisões posteriores recalculam a avaliação canônica.

## Matriz de aceitação

| Requisito | Evidência automatizada |
| --- | --- |
| Campo vazio, localização válida e metas | test_general_search + E2E general-search |
| Uma palavra e dois nichos avançados | test_explicit_interpretation_modes, test_optional_advanced_niches_and_commercial_exclusions + unified-search |
| Texto desconhecido e geografia inválida | test_unknown_text_requires_explicit_review, test_general_requires_real_selected_location + general-search/unified-search |
| Exclusões sem nicho e distribuição da investigação | test_general_research_allocation_is_diverse_and_excludes_incompatible |
| Geoapify e OSM amplos, cobertura incompatível | testes de cada adaptador com respostas controladas em test_general_search; test_search_area |
| Orçamentos, parcial e ranking | test_general_budget_exhaustion_keeps_partial_results, test_general_prefetch_and_final_diversity_preserve_canonical_score, test_smart_search |
| Salvar/reabrir, monitores e rotinas | test_general_saved_reopens_with_filters_and_runs_monitor, test_general_routine_uses_same_worker + general-search/autonomy |
| Histórico e retomada | test_historical_persisted_job_without_mode_resumes_same_query, test_search_compat |
| Pausa/cancelamento, idempotência e isolamento | test_general_pause_resume_cancel_and_ownership, test_empty_launch_and_idempotency_use_one_broad_step + testes existentes do executor |
| Absorção e ausência de contato automático | hashes protegidos, test_absorption, test_absorption_migration, E2E absorption; outbox/drafts vazios no início de busca geral |
| Idiomas, responsividade e teclado | E2E general-search, experience e unified-search; capturas e relatório axe |

Os casos são sintéticos. Aprovação técnica não demonstra aumento de conversão comercial nem cobertura externa de um município.
