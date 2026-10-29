# Validação — v1.38.6-dev

Status: implementação validada localmente em dados sintéticos. Não é homologação externa nem autorização de deploy.

| Verificação | Resultado |
|---|---|
| Backend completo | 551 testes aprovados, incluindo 37 novos |
| Frontend unitário | 27 testes em 8 arquivos aprovados |
| TypeScript aplicação/E2E | Aprovados |
| Vite | Build concluído |
| E2E | 75 testes aprovados em 17 suítes |
| Preservação | 62 fontes/migrações canônicas idênticas ao FULL base |
| Migração | 032 mantida, nenhuma 033 necessária |

## Volume observado

| Empresas | Consultas SQL | Tempo local | Bytes da resposta |
|---|---|---|---|
| 1,000 | 15 | 0.1549 s | 20872 |
| 10,000 | 15 | 2.465 s | 20908 |

Cada cenário possui também uma atividade e uma revisão por empresa. Os 15 comandos incluem autenticação e início do snapshot. A resposta é agregada, sem histórico individual no navegador. Tempos variam com carga do computador e não são SLA. Não houve chamadas reais a provedores.

## Cobertura dos 22 critérios do ciclo

1–3. Identidade única, repetição, origem e múltiplas fontes: `test_sources_deduplicate_same_company_without_merging_homonyms`.
4–6. Histórico parcial, ausência e demo: `test_missing_identity_and_partial_legacy_history_are_not_invented`, `test_empty_data_has_unknown_rates_and_no_fabricated_alerts`, `test_demo_is_excluded_from_every_linked_relation`.
7–10. Retomada, falhas/custos, fusos/DST e denominadores: testes interrupted_resumed, provider_calls, calendar_window e completion_events.
11–14. Rascunho não é contato, declaração/aceitação, associação ambígua e desfecho sem história: testes approved_draft, manual_accepted, reply_requires_traceable, unassociated_message, reply_before_new_acceptance e behavior_never_synthesizes.
15–16. Amostras pequenas e diagnósticos factuais: sources_deduplicate e observed_diagnostics.
17–20. Propriedade, concorrência, idempotência, volume e ausência de efeitos: ownership_on_every_join, concurrent_read, volume_bounded_queries, safety_ceiling, authentication_required, filters_are_closed e rate_limiter. Leitura concorrente não emite INSERT/UPDATE/DELETE nem chama Score/assess.
21. Score e motores preservados por SHA256; testes de regressão e de leitura mantêm versões, critérios e estágio.
22. Suítes históricas completas, incluindo Busca Geral/Unificada, absorção, autonomia, experiência, workflow, redesenho existente, aprendizado, inteligência, comunicação, investigação, fila e acompanhamento.

## Navegador e correções verificadas

Novo E2E usa o endpoint real e registros canônicos sintéticos. Cobre desktop, conta vazia, filtros, proveniência, ausência de requisições por histórico de empresa, falha/retry, redução de movimento, tabelas navegáveis por teclado e larguras 390/320 px. Axe não encontrou violações nas áreas novas cobertas pelos testes; isso não equivale a homologação com leitor de tela.

As duas primeiras execuções encontraram seletores de teste inadequados ao combobox nativo. O seletor passou a usar papel/nome acessíveis e selectOption. A execução seguinte encontrou overflow real no mobile; o grid recebeu coluna minmax(0,1fr) e filhos com min-width:0. A execução final passou após rebuild. Capturas finais estão em qa-v1.38.6-dev.

## Segurança e limites

Revisão do escopo: endpoint autenticado, filtros Literal fechados, proprietário conferido em todos os joins, ORM parametrizado, rate limit 30/min, projeções limitadas, snapshot transacional sem mutação e sem chamadas externas. Não retorna corpos, credenciais, destinatários ou listas de IDs. Campos de agrupamento usam escape do React. Nenhuma dependência nova. Autenticação/CSRF/CORS/cookies, destinatários/opt-out, worker, webhooks e APIs administrativas existentes não foram modificados. Não foram adicionados uploads, SQL/NoSQL dinâmico, eval, comandos com input ou caminhos externos.

Continuam parciais: histórico de descoberta antiga, elegibilidade fora da absorção, classificação quando o índice está vencido/ausente, consumo fora do worker e resultados comerciais incompletos. Permanecem indisponíveis: esforço humano, economia de minutos, custo monetário, chamadas hipotéticas evitadas e tempo até disponibilidade para revisão.

Não homologados: PostgreSQL, provedores reais, produção, HTTPS de implantação, dispositivos físicos, Safari e leitores de tela. Nenhum envio real, deploy ou alteração de banco de produção. Avisos existentes: deprecações Starlette/httpx/anyio e tamanho do chunk de mapas do Vite.

## Evidências e pacotes

Logs e resultados estruturados: qa-v1.38.6-dev/validation.json e arquivos adjacentes. Os recibos externos em release comprovam CRC/hashes, PATCH dry-run, conflito recusado, equivalência com FULL, preservação de runtime, recusa de reaplicação e rollback de fontes. A verificação de extração limpa é registrada em CLEAN-INSTALL-VALIDATION.json após o empacotamento; não é presumida por este documento.
