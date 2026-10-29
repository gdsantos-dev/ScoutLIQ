# Patch 1.23.0 → 1.24.0

Baseline obrigatória: **ScoutLIQ v1.23.0**.

Este patch altera somente frontend e documentação de release. Não contém banco, `.env`, `node_modules`, `dist`, caches ou dados de execução.

## Aplicação
1. Faça backup da instalação atual.
2. Confirme que a base instalada é a v1.23.0.
3. Substitua os arquivos do patch mantendo os caminhos relativos ou use `apply_release_patch.py` incluído no pacote.
4. Execute `npm ci`, `npm test`, `npm run typecheck:e2e` e `npm run build` dentro de `frontend`.
5. Não execute migration por causa deste patch: a v1.24.0 não cria migration.

## Arquivos funcionais principais
- `frontend/src/workspace.css`
- `frontend/e2e/redesign.spec.ts`
- `frontend/src/pages/About.tsx`
- `frontend/src/pages/Settings.tsx`

Oportunidades e Monitores continuam usando `Radar.tsx`; Campanhas e Automações preservam seus handlers e regras atuais. A recomposição deste ciclo é feita pela camada visual/responsiva existente, sem duplicar lógica de produto.
