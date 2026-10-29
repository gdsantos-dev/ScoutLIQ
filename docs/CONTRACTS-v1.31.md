# Contratos de entrega — ScoutLIQ 1.31

## Persistência

Migração aditiva 020 sobre 019. Novos campos em OpportunityEvidence e OutreachDraft; lease, tentativa e retry nas filas existentes; RecipientPolicy e singleton ResearchExecutor. Registros legados recebem valores conservadores, sem autorização de envio inferida. Não há substituição de LeadActivity ou Opportunity Score.

## APIs afetadas

| API | Contrato |
| --- | --- |
| GET /api/leads/{id}/workflow | Evidências/metadados, diagnóstico, cobertura qualitativa e recommendation com comando; score original preservado |
| POST /api/leads/{id}/evidence/capture | Reconcilia última pesquisa confirmada; equivalente renova a mesma observação; divergente substitui com vínculo/auditoria; coleta falha não apaga fatos |
| POST/PATCH /api/leads/{id}/evidence | Categoria/escopo, classificação e motivo explícitos; traduções revisadas para observações livres; controle de versão |
| POST /api/leads/{id}/outreach/drafts | request_id idempotente; estratégia/canal/idioma/destinatário/evidências validados; texto determinístico, sem envio |
| PUT /api/leads/{id}/outreach/drafts/{draft} | Campos de conteúdo permitidos e versão; aprovação anterior invalidada |
| POST .../approve | Aprovação de conteúdo; nota opcional não é prova de consentimento; condição do canal independente |
| POST .../dispatch | Revalida conteúdo e falha fechado; 409 quando indisponível ou 503 sem adapter; nunca transmite |
| GET/PUT /api/leads/{id}/recipient-policy | Política por conta/canal/destinatário exato; declarações não tornam envio elegível; bloqueio e mudanças invalidam drafts relacionados |
| GET /api/research/batches/{id} | Progresso persistido e leads concluídos da própria conta para atualizar a lista |
| POST /api/research/batches/{id}/step | 409 em modo worker; legado explícito usa o mesmo claim atômico |
| POST /api/research/batches/{id}/pause,resume,cancel | Reutiliza fila existente; cancelamento/pausa rechecados antes da gravação |
| POST /api/radar/saved-searches/{id}/schedule | Agenda monitor habilitado no servidor; não executa pesquisa no request |
| PATCH /api/radar/saved-searches/{id}/results | Recusa autoridade do browser quando monitor é executado em modo worker |
| Exportação privada existente | Mantém schema global 13; opportunity_workflow_version=2 acrescenta políticas e metadados sem hash de aprovação |

Todas as rotas específicas exigem sessão e propriedade; mutações herdam CSRF/Origin e rate limiting. Não confiar em IDs do frontend. Detalhes de segurança e limites: SECURITY-GATE-v1.31.md.

## Arquivos centrais

- backend/evidence_intelligence.py: catálogo, TTL, reconciliação, diagnóstico e decisão contextual.
- backend/outreach_intelligence.py: identidade exata de destinatário, condição de canal, localização e composição.
- backend/research_worker.py e backend/monitor_matching.py: execução persistente e filtros dos monitores.
- backend/opportunity_workflow.py, opportunity_models.py, models.py e main.py: contratos existentes estendidos.
- migrations/versions/020_applied_intelligence.py: evolução aditiva.
- frontend/src/components/OpportunityWorkflow.tsx, opportunity-workflow.css, ContextPanel.tsx, OutreachComposer.tsx: operação/revisão/edição e bloqueios.
- frontend/src/pages/Radar.tsx: consulta do progresso e agendamento no servidor.
- frontend/src/workspace.css: correções responsivas e acessibilidade.

A lista completa por hash fica no CHANGED-FILES.json e no PATCH-MANIFEST.json, incluindo testes, documentação, versão e ferramentas de empacotamento.
