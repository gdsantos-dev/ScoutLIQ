# Validação — ScoutLIQ 1.25.0

## Resultado local do release
- `PYTHONPATH=. pytest -q`: **107 testes passaram**.
- Parse/transpilação sintática de `frontend/src/**/*.{ts,tsx}` e `frontend/e2e/**/*.{ts,tsx}`: **0 diagnostics** nos arquivos executáveis.
- JSONs do release: parse válido.
- `frontend/src/styles.css`, `frontend/src/workspace.css` e `frontend/src/tokens.css`: chaves balanceadas, saldo final **0**.
- Comparação contra a v1.24.0: **46 arquivos protegidos de backend/runtime conferidos, 0 diferenças**.
- Backend e migrations permanecem byte a byte iguais à baseline v1.24.0.

## Frontend completo
`npm ci --prefer-offline --no-audit --no-fund` foi tentado, mas o ambiente de geração não conseguiu concluir a instalação dentro da janela disponível. Uma tentativa offline confirmou que o cache local não contém todas as dependências (`ENOTCACHED`, pacote `yallist-3.1.1.tgz`).

Por isso, `npm test`, `npm run typecheck:e2e`, `npm run build` e Playwright não foram considerados validação concluída neste ambiente. O arquivo E2E recebeu invariantes específicas da v1.25.0 para serem executadas no ambiente de desenvolvimento/deploy com `npm ci` completo.

## Invariantes visuais adicionadas ao E2E
- Não existe mais `.environment-dot` no shell.
- O fundo global não possui imagem/gradiente decorativo.
- Cabeçalhos de página não dependem de borda inferior.
- Masthead e navegação mobile não usam backdrop blur.
- Overflow horizontal continua proibido nos cenários responsivos.

## Regressão protegida
- Sem migration nova.
- Sem mudanças em `backend/`.
- Sem mudanças em `migrations/`.
- Sem mudanças em `alembic.ini`, requirements, Dockerfile, Railway ou lock de runtime Python.
- `.env`, banco, `node_modules`, `dist` e diretórios de execução são excluídos dos artefatos.

## Validação visual recomendada
Em 390×844 e desktop 1440px+, conferir:
- hierarquia de títulos sem linhas redundantes;
- proximidade label/campo em formulários;
- contraste dos hairlines em tabelas e listas;
- estados ativos usando crimson apenas quando necessário;
- bottom navigation e masthead sólidos;
- estados vazios compactos e alinhados ao conteúdo;
- modais/sheets sem aparência de glass genérico.
