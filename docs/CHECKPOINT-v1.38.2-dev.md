# Checkpoint — v1.38.2-dev

Implementação e validação local concluídas em 24/10/2026. A confirmação de integridade dos pacotes está em `release/PACKAGE-VALIDATION.json`, gerado pelo empacotador; ele deve indicar todas as verificações como verdadeiras antes de usar os ZIPs.

## Ponto exato de retomada

Use `work/v1.38.2-dev/ScoutLIQ` ou extraia o novo FULL. Base do PATCH: FULL v1.38.1-dev, SHA256 `2a92b87a7eb4c0d513698df05fc18dca7ac5e3d373d41a6a0d0b42bcb7879229`. Checksums dos novos pacotes: `release/SHA256SUMS.txt`. O `RELEASE-MANIFEST.json` confere cada fonte/captura incluída.

Não repetir Absorção, P0.1, Score, Busca Unificada ou redesign. Este ciclo entrega JSON/CSV/tabela, mapeamento e originais, edição versionada, auditoria, deduplicação, recuperação pelo worker/cache/Geoapify opcional, revisão de candidatos, pausa/retomada/cancelamento, confirmação incremental e migração aditiva 029.

Próximo ciclo funcional: investigação progressiva após a entrada no Radar, usando o worker existente e a proveniência `external_absorption` em LeadActivity. Essa investigação NÃO foi ligada automaticamente. Contatos, campanhas e mudanças no Score exigem escopo próprio. Antes de uso real da recuperação externa, homologar uma consulta controlada com credenciais e orçamento explícitos; não presumir cobertura/custo ou qualidade comercial pela validação sintética.

## Evidências e reprodução

- Backend integral: 407 aprovados (`artifacts/backend-final.txt`). Após 5 novos casos de parsing, repetição de 59 focados aprovada (`artifacts/absorption-delivery-tests.txt`). Total de 412 casos distintos verificados, sem somar repetições.
- Frontend: 23 aprovados, build e tipagem E2E aprovados.
- E2E: 65 aprovados em 13 suítes, incluindo retestes finais de Absorção nas portas 8360/8361. A fixture semântica antiga foi corrigida após reprodução da mesma falha na base (8340); passou no candidato (8351). Nenhum motor de busca foi alterado.
- SQLite: 028→029, instalação limpa, integridade, FKs, versões e recusas de downgrade testadas. Não homologado em PostgreSQL.
- 36 arquivos protegidos idênticos à base; mapa de hashes em `docs/qa-v1.38.2-dev/validation-evidence.json`.
- Capturas desktop/320/390 no diretório `docs/qa-v1.38.2-dev` do FULL e do PATCH.

Python local: `../../../.venv/Scripts/python.exe`. Usar TEMP/TMP e `--basetemp` em `artifacts/tmp`. Frontend usa dependências instaladas por junção local; a junção não integra pacotes. Compile o frontend antes de importar backend.

Reproduzir: `python -m pytest -q`; frontend `npm test`, `npm run build`, `npm run typecheck:e2e`; navegador `python scripts/validate_browser_v1382.py --group complete --port 8500`, com portas/bancos sintéticos novos. Não relançar fixture sobre banco existente. Não apontar testes para dados pessoais.

Empacotar: `python scripts/package_absorption_v1382.py --base ../../v1.38.1-dev/ScoutLIQ/release/ScoutLIQ-v1.38.1-dev-FULL.zip`. O script testa aplicação/rollback somente em instalações descartáveis.

## Limites preservados

Sem deploy, banco pessoal alterado, cota externa real ou comunicação comercial. Recuperação externa limitada a Geoapify já configurado; cidade/país obrigatórios para delimitação, 5 candidatos, ambiguidades pendentes. OSM/demo permanecem sem recuperação externa compatível. Cache/manual funcionam sem nova API paga. Originais, correções e jobs impedem downgrade destrutivo da 029; restaure backup consistente de banco e código quando necessário.
