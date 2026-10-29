# Patch 1.21.0 → 1.22.0

Baseline obrigatória: **ScoutLIQ v1.21.0**.

Este patch altera somente frontend e documentação de release. Não contém banco, `.env`, `node_modules`, `dist` ou dados de execução.

## Aplicação
1. Faça backup da pasta atual.
2. Confirme que a base instalada é a v1.21.0.
3. Substitua os arquivos do patch mantendo os caminhos relativos.
4. Execute `npm ci`, `npm test`, `npm run typecheck:e2e` e `npm run build` dentro de `frontend`.
5. Não execute migration por causa deste patch: a v1.22.0 não cria migration.

## Arquivos funcionais principais
- `frontend/src/pages/Radar.tsx`
- `frontend/src/components/ContextPanel.tsx`
- `frontend/src/components/UI.tsx`
- `frontend/src/workspace.css`
- `frontend/e2e/redesign.spec.ts`

Os demais arquivos do patch atualizam versão, documentação e manifest de release.
