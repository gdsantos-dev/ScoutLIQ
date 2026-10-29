# Changelog — v1.38.5-dev

- Acompanhamento integrado ao Pipeline e à Fila Comercial, com filtros e prioridade operacional explicável, preservando Score 3.0.
- Planejador local distingue rascunho, aprovação, execução, aceitação, entrega desconhecida e respostas conservadoras.
- Intervalo por usuário/fuso, pausa, conclusão por evento, desativação e retomada por empresa.
- Próximas ações manuais protegidas; substituição/conclusão em lote exige consentimento explícito e prévia.
- Follow-ups/respostas pelo compositor e editor canônicos, sem duplicação por evento/canal/destinatário/idioma.
- Registros manuais no LeadActivity com proveniência, data, resultado, observações e idempotência, sem recibo falso de provedor.
- Respostas Gmail preservam próxima ação preenchida; associação estrita e escopo da sincronização mantidos.
- Confirmação compartilha a trava curta canônica de comunicação; bloqueios e versões são revalidados.
- Migração 032 aditiva e downgrade protegido; export inclui preferências.
- Teste de volume cria `artifacts/` automaticamente. Importação para testes sem frontend compilado não falha no mount de assets.
- Sem deploy, novo worker, IA paga, envio automático, desbloqueio de contato ou redesign.
