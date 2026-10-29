# Validação — v1.38.7-dev

Status: implementado e validado localmente em bancos isolados e adaptadores sintéticos. Sem homologação externa ou autorização de deploy.

| Verificação | Resultado |
|---|---|
| Backend completo | 592 testes aprovados, 41 novos |
| Frontend unitário | 27 testes aprovados |
| TypeScript aplicação/E2E | Aprovados |
| Vite | Build concluído |
| E2E | 77 testes aprovados em 18 suítes |
| Preservação | 61 fontes/migrações canônicas idênticas ao FULL base |
| Migração | 033 sobre 032; preservação e recusa de downgrade destrutivo testadas |

## Volume

| Empresas | Consultas de progresso | Tempo local | Provedores |
|---|---|---|---|
| 1,000 | 8 | 0.0138 s | 0 |
| 10,000 | 8 | 0.0441 s | 0 |

A consulta usa agregações SQL sem carregar a lista de Leads. A contagem de consultas permanece constante. Tempos locais não são SLA nem homologação PostgreSQL. O scheduler não chama o relatório completo de Inteligência.

## Cobertura dos 27 critérios obrigatórios

| Critérios | Evidência |
|---|---|
| 1–2. Desativado e consentimento | `test_disabled_creation_and_explicit_current_preview` e E2E de autorização |
| 3. Metas 25/50/75/100 | `test_configurable_goal_and_first_canonical_incorporation`, parametrizado |
| 4–5. Unicidade e múltiplas origens | `test_manual_and_absorption_origins_count_once_demo_and_existing_do_not`; crédito explicitamente vinculado |
| 6–8. Busca geral, direcionada e dois locais | `test_two_authorized_locations_general_search_priority_and_neutral_fallback` |
| 9–10. Reencontro e nenhum resultado | Testes de duas pesquisas sobre a mesma identidade e `test_no_new_results_exhausts_only_authorized_search` |
| 11–14. Cooldown, limites, meta e orçamento | `test_daily_limit_and_cooldown`, `test_goal_reached_by_other_ingress_prevents_new_work`, `test_operation_budget_reserved_atomically_for_plan` |
| 15–16. Fonte e busca indisponíveis | `test_unavailable_provider_and_global_limit_do_not_create_job`, `test_existing_search_blocks_plan_without_cancelling_it` |
| 17–18. Concorrência e reinício | `test_two_workers_one_plan_one_canonical_job_and_restart_recovery`; reabertura de sessão e recuperação de lease |
| 19–20. Pausa, retomada, desativação e histórico | `test_pause_fences_inflight_resume_disable_keep_history_and_saved_config`; E2E com página fechada |
| 21–22. Sugestões sem evidência e com fatos | Testes de sugestões sem dados e backlog observado, com período/população/contagem |
| 23. Isolamento | DTO, ownership, CSRF, autenticação, duas contas e progresso separado |
| 24. Integridade das rotinas/jobs | Regressão de autonomia, caminho único `schedule_saved`, hashes de preservação |
| 25. Ausência de envio | Somente discovery/research nos planos; nenhum hook em comunicação; adapters simulados e regressão de comunicação |
| 26. Inteligência Operacional | Suíte backend e E2E `operations` preservadas |
| 27. Regressão histórica | Backend completo e 17 suítes anteriores de navegador |

Cobertura adicional: resultados acima do limite do adaptador, descarte sem crédito, DST, fairness entre contas, prevenção de loops sem orçamento e recusa de exclusão que apagaria vínculos do orçamento diário.

## Evidência visual

`qa-v1.38.7-dev/planning-desktop.png`, `planning-progress-desktop.png`, `planning-390.png` e `planning-320.png`. Chromium local, 1440 px desktop e 390/320 px mobile, redução de movimento, teclado, erro/retry e Axe WCAG A/AA. Não substitui testes em dispositivo físico, Safari ou leitor de tela. Ajustes finais de checkbox e remoção explícita de pesquisa fora da lista são cobertos no E2E final de planejamento; não houve remake.

## Segurança e limites

Entrada validada no backend, DTO com campos permitidos, ownership de pesquisas/plano e joins de crédito, ORM parametrizado, autenticação/CSRF existentes, rate limits e autorização por prévia atual. Fencing e reservas persistentes impedem duplicidade e ultrapassagem de orçamento; nenhum provedor é chamado ao abrir a interface. Conteúdo é renderizado por React sem HTML arbitrário.

Não foram adicionados upload, webhook, login, pagamento, segredo no frontend ou caminho de execução de comandos externos. Autenticação, sessões, headers, CORS, opt-outs e comunicação existentes foram preservados e submetidos à regressão. Dependências não mudaram. Não foi efetuada nova auditoria de CVEs em serviço externo nem revisão de produção: esta entrega não é deploy.

## Limitações e estados

- **Implementado/testado localmente:** plano, consentimento, execução no worker existente, limites, progresso, sugestões, histórico e UI.
- **Parcial:** descartes históricos sem observação antes de 033; histórico recalculado após exclusões; comparação de dias após alteração de fuso. Esses dados não geram otimização automática.
- **Delimitado:** um plano por conta; até 20 pesquisas; máximo de uma execução por pesquisa/dia; cooldown mínimo 24 h; janela no mesmo dia; histórico até 366 dias/200 decisões exibidas; opções até 200 pesquisas com aviso.
- **Sem dados verificáveis:** custo monetário e lucratividade. Não estimados.
- **Não homologado externamente:** PostgreSQL, provedores reais, produção/HTTPS, Safari, dispositivos físicos e leitores de tela.

Não houve envio comercial, uso de cota externa, deploy ou alteração de banco de produção. Permanecem avisos já existentes de depreciação Starlette/anyio e tamanho do chunk de mapa do Vite.

## Distribuição

Os recibos externos `release/PACKAGE-VALIDATION.json` e `release/CLEAN-INSTALL-VALIDATION.json` registram verificação de hashes, equivalência PATCH/FULL, proteção de runtime, recusa de conflito/reaplicação, rollback de fontes e teste em extração limpa. O relatório de fonte não se autoatribui os hashes dos ZIPs. Consulte os recibos após o empacotamento.
