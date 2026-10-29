# Patch 1.24.0 → 1.25.0

Baseline obrigatória: **ScoutLIQ v1.24.0**.

Este patch altera somente frontend e documentação de release. Não contém banco, `.env`, `node_modules`, `dist`, caches ou dados de execução.

## Aplicação
1. Faça backup da instalação atual.
2. Confirme que a base instalada é a v1.24.0.
3. Substitua os arquivos do patch mantendo os caminhos relativos ou use `apply_release_patch.py` incluído no pacote.
4. Execute `npm ci`, `npm test`, `npm run typecheck:e2e` e `npm run build` dentro de `frontend`.
5. Não execute migration por causa deste patch: a v1.25.0 não cria migration.

## Arquivos funcionais principais
- `frontend/src/workspace.css`
- `frontend/src/components/WorkspaceShell.tsx`
- `frontend/src/pages/About.tsx`
- `frontend/src/pages/Settings.tsx`
- `frontend/e2e/redesign.spec.ts`

O release é um ciclo de acabamento visual. Os handlers, páginas, endpoints e regras existentes continuam sendo os mesmos da v1.24.0.
