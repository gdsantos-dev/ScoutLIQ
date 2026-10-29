# Validação — ScoutLIQ 1.24.0

## Resultado local do release
- `pytest -q`: **107 testes passaram**.
- Transpilação sintática de todos os arquivos `frontend/src/**/*.{ts,tsx}` e `frontend/e2e/**/*.{ts,tsx}` com TypeScript: **0 diagnostics**.
- `frontend/src/workspace.css`: estrutura de chaves validada, saldo final **0**.
- Comparação da v1.23.0 com a árvore da v1.24.0: **42 arquivos protegidos de backend/runtime conferidos, 0 diferenças**.
- Backend e migrations permanecem byte a byte iguais à baseline v1.23.0.

## Frontend completo
A instalação de dependências foi tentada com `npm ci --prefer-offline --no-audit --no-fund`, mas o ambiente de geração não conseguiu resolver/downloadar pacotes do `registry.npmjs.org` (`EAI_AGAIN`) e a execução precisou ser interrompida. Por isso, `npm test`, `npm run typecheck:e2e`, `npm run build` e Playwright não foram executados neste ambiente.

A suíte E2E foi estendida com um cenário mobile cobrindo Oportunidades, Monitores, Campanhas, editor de Automações, Configurações e About. Esse cenário deve ser executado no ambiente de deploy/desenvolvimento com as dependências instaladas.

## Regressão protegida
- Sem migration nova.
- Sem mudanças em `backend/`.
- Sem mudanças em `migrations/`.
- Sem mudanças em `alembic.ini`, requirements ou lock de runtime Python.
- `.env`, banco e diretórios de execução são excluídos dos artefatos.

## Validação visual recomendada antes da v1.25.0
Em viewport de aproximadamente 390×844, conferir:
- Oportunidades e Monitores sem overflow horizontal.
- Campanhas com seleção horizontal e detalhe contínuo.
- Editor de Automações ocupando a área entre masthead e navegação inferior.
- Configurações em fluxo vertical e botões com alvo touch.
- About sem colunas comprimidas.
- Modais de cadastro/venda/pagamento/custo abrindo como sheets e mantendo ações alcançáveis.
