# Checkpoint — v1.38.7-dev

Base v1.38.6-dev FULL verificada por hash/CRC; revisão 032. Implementação local na cópia isolada `work/v1.38.7-dev/ScoutLIQ`, nova revisão 033. Não reiniciar o desenvolvimento da feature nem reimplementar scheduler/worker.

Código: `backend/prospecting.py`, `backend/prospecting_models.py`, migração 033 e hooks pequenos em routines, consumption, smart_search e main. UI em `frontend/src/components/ProspectingPlan.tsx`, integrada em Automações. Arquitetura, contratos e limitações nos documentos desta versão.

Validação funcional: 592 backend, 27 unitários frontend, TypeScript/Vite e 77 E2E aprovados. Evidências em `docs/qa-v1.38.7-dev`. Comparação por hashes preserva 61 fontes/migrações canônicas.

Gate final de distribuição: executar `scripts/package_planning_v1387.py --base ../../v1.38.6-dev/ScoutLIQ/release/ScoutLIQ-v1.38.6-dev-FULL.zip` e `scripts/verify_planning_clean_install.py`; conferir os recibos externos PACKAGE-VALIDATION e CLEAN-INSTALL-VALIDATION em release. A existência dos recibos aprovados e os hashes dos ZIPs são o checkpoint verificável de entrega, não este texto isolado.

Retomada futura: usar o FULL v1.38.7-dev identificado em `release/SHA256SUMS.txt`, validar manifesto e recibos, preservar runtime e aplicar migração 033 conforme INSTALL. Não considerar homologados provedores/PostgreSQL/produção/dispositivos físicos. Não autorizar envios a partir do plano. Homologações externas exigem ambiente e credenciais próprios e autorização correspondente.
