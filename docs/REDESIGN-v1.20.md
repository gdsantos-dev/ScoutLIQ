# ScoutLIQ 1.20 — redesign da experiência

## Fontes e etapa zero

Base única: `ScoutLIQ-v1.19.1-campaigns-typescript-hotfix-full.zip`, fornecido pelo usuário.
Direção de UX: `ScoutLIQ_v1.19.1_Handoff_Redesign_Premium.md`, lido integralmente junto com o pedido colado. O pedido atual autoriza implementar após a conferência técnica. A instrução de aguardar no handoff descrevia uma etapa anterior.

O documento `ScoutLIQ_v1.19.1_Auditoria_Arquitetura_Redesign.md` não acompanha os materiais. O usuário esclareceu que a referência técnica é o ZIP hotfix. `docs/REDESIGN_AUDIT.md` dentro dele é uma auditoria anterior da v1.0. Esta divergência foi registrada antes da implementação.

## Inventário conferido no hotfix

| Sistema preservado | Código / contrato | Nova superfície |
| --- | --- | --- |
| Descoberta, geocodificação, raio, região, bounds, polygon | Radar.tsx, radar_query.py, /radar/search, /radar/locations | Operar / Radar |
| MapLibre, seleção e território | OpportunityMap.tsx, OpenOpportunityMap.tsx | Canvas operacional |
| Filtros, listas inteligentes, similares | Radar.tsx, /leads/{id}/similar | Oportunidades / Radar |
| Buscas salvas e monitoramento | RadarSavedSearch, /radar/saved-searches | Monitores e buscas no Radar |
| Watchlist e mudanças | Lead.watchlisted, /leads/{id}/watchlist, Activities | Monitores e contexto |
| Score, confiança, timing, estrutura, fit e concorrentes | scoring.py, Lead.score | Contexto / Análise |
| Research, audit, reanálise e enrichment | research.py, enrichment.py | Contexto / Pesquisa |
| Pesquisa em lote | ResearchBatch, /research/batches | Radar e Monitores |
| Trigger → Condição → Ação | automation.py, AutomationRule / AutomationRun | Menu de workspace / comandos |
| Campanhas, attribution e outcomes | Campaign / CampaignLead, /campaigns, /insights/outcomes | Operar / Campanhas |
| Pipeline, próximas ações e histórico | Lead, LeadActivity | Gerir clientes / Negociações |
| Cliente derivado | Lead ganho + Sale + Payment + Site + Activities | Clientes e contexto |
| Sites, domínio, manutenção, receita e SSL | Site, Sites.tsx, /sites | Sites / Entregas |
| Vendas, recebimentos, custos e exportação | Sale / Payment / Expense, /dashboard, /export | Financeiro |
| Conta, autenticação, preferências e i18n | AuthScreen, Settings, i18n, security.py | Workspace / Configurações |

Não existe Client table e nenhuma é necessária. A migration terminal do pacote é 018. Os dois arquivos nomeados 007 têm revisões distintas; a cadeia real é verificada por Alembic.

## Decisões

- Operar: superfície espacial, navegação compacta e resultados progressivos. Gestão: ações pendentes, relações e listas.
- Overview sai da navegação. Seu valor é distribuído por contexto, sem dashboard de cartões.
- Context Panel com Resumo, Análise, Pesquisa e Relacionamento substitui o painel monolítico; mantém operações existentes.
- Neutros acromáticos e crimson. Accents legados permanecem no banco; a UI aplica a identidade ScoutLIQ.
- Texto de operação de 14–16px, alvos de toque de 44px e movimento curto com redução respeitada.
- Referências consultadas: [ORLIQ](https://orliq.com.br/), [Mercedes Hyperscreen](https://group.mercedes-benz.com/technology/digitalisation/connectivity/mbux-hyperscreen.html), [Refero Mercury](https://styles.refero.design/style/3172cd4d-118a-4a16-a259-6b634d32322e), [Felt](https://help.felt.com/getting-started/tour-the-interface), [Attio](https://attio.com/help/reference/managing-your-data/views/create-and-manage-table-views), [Mapbox](https://docs.mapbox.com/console-tools/studio/studio-interface/). Estudos de contenção, continuidade e interação, filtrados pelo handoff.

## Fases internas

A. Tokens, legibilidade e controles. B. Dois ambientes e comandos. C. Radar, oportunidades, monitores, contexto e campanhas. D. Negociações, clientes, sites e financeiro. E. Estados, teclado, mobile, validação e pacote.

Resultados e limites são registrados em VALIDATION-v1.20.md ao final.
