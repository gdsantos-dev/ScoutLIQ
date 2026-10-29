# Checkpoint — ScoutLIQ v1.35 / Prompt 2 de 3

Base exclusiva: work/v1.34.0/ScoutLIQ/release/ScoutLIQ-v1.34.0-full-source.zip, SHA256 46f5b86e0ab08441a73843648a0a3e49d6027b1c930b64186ab1a6c623e34582. Trabalho: work/v1.35.0/ScoutLIQ. Não reiniciar pelo código da raiz, refazer P0.1/P0.2 ou iniciar Prompt 3.

## Implementado

P0.3: importação/revisão/histórico, datasets e métricas, calibração aprovada e rollback, UX na ficha e Histórico. commercial_learning.py, learning_models.py, selection_quality.py, score_criteria.py, score_calibration.py, CommercialLearning/ScoreCalibration. Migrações 024/025.

P0.4: communication_models.py, communication.py, communication_replies.py, gmail_adapter.py, gmail_oauth.py, channel_contract.py. Migração 026. ResearchExecutor/worker e ledger existentes; outbox/idempotência/cancelamento/uncertain/reconcile; OAuth/cifra/reconnect/revoke; replies/cursor/associação/CRM/supressão. Componente Communication na ficha e Integrações.

Guias LEARNING, COMMERCIAL-MATRIX, COMMUNICATION, GMAIL, INSTALL, CHANGELOG e SECURITY-GATE v1.35. GMAIL-DESIGN-v1.35 é uma nota histórica de preparação, substituída pelo guia operacional GMAIL-v1.35.

## Estado consolidado

Backend completo final: 265 aprovados, incluindo thread com referências a duas oportunidades, isolamento, recuperação e migrações. Frontend: 23. Build/typecheck aprovados; supervisor real com prontidão, queda/restart/shutdown aprovados. Score padrão com resultados completos iguais ao código do ZIP v1.34 em 175 casos controlados. pip-audit e npm audit: zero vulnerabilidades conhecidas.

40 E2E distintos aprovados em três grupos: 33 legado, 6 autonomia/inteligência/aprendizado, 1 comunicação. Worker separado, aceitação controlada e reply na mesma oportunidade; reflow 320/390/768/1440 e axe nas novas funções. Logs: artifacts/e2e-legacy-v135.txt, artifacts/e2e-intelligence-v135.txt, artifacts/e2e-communication-v135.txt e artifacts/pytest-release-v135.txt. Relatório completo: VALIDATION-v1.35.md.

## Entrega e reprodução

FULL e PATCH estão em release, junto com SHA256SUMS.txt e CHANGED-FILES.json. O FULL contém migrações 024–026, guias, testes e manifesto. PATCH parte exclusivamente da base exata indicada acima. Verificação: 307 fontes + manifesto, 62 entradas de patch, aplicação reproduz o FULL; dry-run não escreve; backup confere; conflitos/reaplicação recusados; runtime preservado/excluído dos pacotes.

Para reproduzir, executar scripts/build_release.py e scripts/verify_release.py com --base ../../v1.34.0/ScoutLIQ/release/ScoutLIQ-v1.34.0-full-source.zip. Reempacotar após qualquer alteração em fonte/docs e verificar novamente. Nunca incluir .env, tokens, bancos, dependências, caches ou artifacts de QA nos ZIPs de código. Não incrementar versão só por troca de janela.

## Pendências delimitadas

Sem casos ORLIQ reais: qualidade comercial/ganho de conversão não medidos. Gmail real exige cliente OAuth, credenciais, consentimento/PKCE/scopes, revisão Google aplicável e autorização específica para homologação. Nenhum envio real realizado.

DNS automático não implementado; existe revisão manual. Recuperação de histórico Gmail limitada, com cobertura parcial quando truncada. Sem associação manual de mensagens ambíguas; revisar na caixa Gmail. WhatsApp P1 é contrato compartilhado sem adapter/templates/webhooks, a desenvolver em fatia própria com o mesmo motor. P0.3 limitado a 2.000 casos e 5.000 Leads por aplicação de critérios. Deploy/HTTPS/PostgreSQL/Docker/dispositivos físicos pendentes. Detalhes nos guias; fixtures não comprovam produção.

Próxima retomada: usar esta v1.35 consolidada. Primeiro trabalhar com casos revisados reais e/ou homologação OAuth autorizada conforme insumos disponíveis. Para continuar tecnicamente sem credenciais, as fatias delimitadas são diagnóstico DNS, revisão manual de ambiguidades e adapter oficial WhatsApp. Não reconstruir mecanismos concluídos nem iniciar redesign sem a solicitação correspondente.
