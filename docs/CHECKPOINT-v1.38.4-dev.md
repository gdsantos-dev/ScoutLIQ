# Checkpoint — v1.38.4-dev

Pasta integrada: `work/v1.38.4-dev/ScoutLIQ`. Base de comparação: v1.38.3-dev exata. Não reiniciar a implementação a partir das versões antigas.

## Arquivos centrais

- `backend/commercial_review.py`: índice canônico, fila, resumo, prévia, confirmação, idempotência e export.
- `backend/commercial_review_models.py`: decisões e operações persistidas.
- `backend/opportunity_workflow.py`: serviço canônico `create_draft`, compartilhado com o endpoint individual.
- `frontend/src/components/CommercialQueue.tsx`: lista, seleção, prévia e integração com o editor existente.
- `frontend/src/pages/Radar.tsx`: alternância entre descoberta e revisão.
- `migrations/versions/031_commercial_review.py`: upgrade sobre 030 e recusa de downgrade destrutivo.
- `tests/test_commercial_review.py`, `test_commercial_review_migration.py` e `frontend/e2e/commercial-queue.spec.ts`: provas do novo fluxo.

Leia `VALIDATION-v1.38.4-dev.md` e os recibos de distribuição para conhecer os resultados efetivamente concluídos. O relatório é gerado somente após verificar as execuções locais; não inferir aprovação de uma etapa pela existência deste checkpoint.

## Próximo ciclo

Preservar as decisões humanas, o compositor canônico e a separação preparação/aprovação/condição de contato/autorização/envio. Não introduzir comunicação em lote como extensão implícita desta entrega.

Homologação externa pendente: PostgreSQL do ambiente-alvo, implantação HTTPS, navegador/dispositivos físicos e avaliação comercial com casos reais revisados da ORLIQ. Atualizar auditoria de dependências antes de publicação. Não houve autorização de deploy nem de envio real.

Para validar pacotes novamente, extraia o FULL e execute `scripts/verify_commercial_package.py`; o recibo externo verifica os ZIPs, enquanto o interno verifica fontes. O PATCH aplica somente sobre a base cujo hash está em `INSTALL-v1.38.4-dev.md`.
