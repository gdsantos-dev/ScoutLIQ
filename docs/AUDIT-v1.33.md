# Auditoria da base e decisão de implementação

Base exclusiva: FULL 1.32.0, SHA256 `a4afe91edc0f626d732cfa2781e947a69f79991b3df0c0e180d0de72303104f7`. Os 239 arquivos do manifesto foram conferidos antes da extração para uma pasta nova. A raiz pessoal, a baseline 1.20 e a instalação 1.32 não foram editadas. Nenhum banco ou .env pessoal foi copiado.

| Mecanismo confirmado no código 1.32 | Decisão na primeira fatia |
|---|---|
| `smart_search.py`, `search_intent.py`: intenção validada, metas 25/50/75/100, estado/cursor persistidos | Extrair criação de job reutilizável; rotinas chamam o mesmo fluxo. Interpretador permanece determinístico. |
| `commercial_fit.py`, `scoring.py`, `scoring_legacy.py`: adequação compartilhada, prioridade 3.0, snapshot 2.5 | Não alterar fórmula/pesos. Usar prioridade existente na seleção de investigações vencidas. |
| `search_sources.py`, `providers.py`: capacidades explícitas, Geoapify paginado, OSM limitado | Não adicionar fontes nem alegar cobertura nova; registrar fonte autorizada e bloquear mudança silenciosa entre execuções. |
| `ResearchExecutor`, `research_worker.py`: uma concessão global, token, lease, orçamento, backoff | Acrescentar ledger, agendador e heartbeat; conservar exclusão mútua e transação de resultados. |
| `ResearchBatch`, `ResearchBatchItem` | Reutilizar para investigação; pausa/cancelamento da rotina controla os filhos e impede retomada indevida por rota legada. |
| `research.py`, `LeadResearch` | Instrumentar operações dos adapters e propagar contexto aos pools. Não criar outro investigador nem mudar o algoritmo de diagnóstico. |
| `OpportunityEvidence`, `evidence_intelligence.py` | Conservar validade, proveniência, contradições, revisão e vínculo com pesquisa. O fluxo persistente existente incorpora novas observações. |
| `OpportunityWorkflow.tsx`, `opportunity_workflow.py`: Ficha Operacional | Resultados das rotinas abrem a Busca/Ficha existentes. Nenhum CRM ou painel de investigação duplicado. |
| `OutreachDraft`, `RecipientPolicy`, `outreach_intelligence.py` | Preservar conteúdo, aprovação e recusa por destinatário. Aprovação continua sem habilitar envio. |
| `RadarSavedSearch`: query, versão, monitor territorial | Campos aditivos guardam objetivo, critérios, limites, estado, agenda e repetição comercial. Não ativar monitor territorial junto. |
| `automation.py`, `AutomationRule`, `AutomationRun` | Manter regras/ações e idempotência existentes. Nova seção operacional usa a página Automações existente. |
| `Lead`, `LeadActivity`, pipeline, vendas/finanças/Sites | Mesma identidade, histórico e efeitos transacionais; novos eventos de configuração ficam em histórico próprio da rotina. |
| `security.py`, middleware/main, bootstrap | Reutilizar sessões/Argon2/CSRF, autorização por proprietário, versões otimistas, erros seguros. |
| Docker/start.py/Railway, Alembic 021 | A base iniciava somente web. Implementar supervisor combinado e migração 022 aditiva, sem PostgreSQL obrigatório. |

## Limites encontrados

A base não implementa LLM semântico, planejamento entre múltiplas fontes, importação supervisionada de casos reais, OAuth Gmail, outbox comercial ou respostas recebidas. Nada disso foi renomeado como concluído. Cobertura de fonte continua sendo o contrato existente, não prova de resultados reais em um território.

O primeiro incremento foi P0.1: worker, recorrência, limites e recuperação. O trabalho de inteligência P0.2 depende desta execução persistente; seu próximo passo está no changelog. A instrumentação de `research.py` muda o arquivo, mas os motores de score, evidências, outreach e regras existentes são conferidos byte a byte no verificador de release.
