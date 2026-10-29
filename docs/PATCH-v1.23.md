# Patch 1.22.0 → 1.23.0

Baseline obrigatória: **ScoutLIQ v1.22.0**.

Este patch altera frontend e documentação de release. Não contém banco, `.env`, `node_modules`, `dist`, caches ou dados de execução.

## Aplicação
1. Faça backup da instalação atual.
2. Confirme que a base instalada é a v1.22.0.
3. Substitua os arquivos do patch mantendo os caminhos relativos.
4. Execute `npm ci`, `npm test`, `npm run typecheck:e2e` e `npm run build` dentro de `frontend`.
5. Não execute migration por causa deste patch: a v1.23.0 não cria migration.

## Arquivos funcionais principais
- `frontend/src/pages/Clients.tsx`
- `frontend/src/pages/Sites.tsx`
- `frontend/src/pages/Finance.tsx`
- `frontend/src/workspace.css`
- `frontend/e2e/redesign.spec.ts`

`Pipeline.tsx` mantém sua estrutura funcional; a recomposição de Negociações é feita pela camada visual mobile. Os demais arquivos do patch atualizam versão, documentação e manifest de release.
