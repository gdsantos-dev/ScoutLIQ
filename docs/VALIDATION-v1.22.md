# Validação v1.22.0

## Escopo protegido
- Backend: sem alteração de arquivo em relação à v1.21.0.
- Banco e migrations: sem alteração.
- Contratos de API: sem alteração.
- Score Engine, Research & Automation e regras comerciais: sem alteração.
- Desktop: nenhuma reconstrução estrutural; as novas regras visuais do Radar são limitadas por media query mobile.

## Cenários de interface cobertos pelo release
- Radar abre em mapa no viewport mobile.
- Busca permanece utilizável sem overflow horizontal.
- Bottom sheet de resultados alterna entre `peek`, `mid` e `full`.
- Filtro local aparece a partir de `mid`.
- Ações da área visível e território continuam acessíveis acima do sheet.
- Pesquisa, filtros e buscas salvas funcionam como sheets mobile.
- Abrir uma empresa mostra contexto compacto; detalhes expandem a superfície.
- Navegação inferior e masthead da v1.21.0 permanecem preservados.
- Viewports de referência do cenário E2E: 320×844 e 390×844.

## Resultado executado na geração
- Reconstrução da baseline v1.21.0 validada contra o `RELEASE-MANIFEST.json`: **159/159 arquivos**, 0 ausentes e 0 hashes divergentes.
- Backend e migrations comparados com a v1.21.0: **0 arquivos divergentes**.
- Suíte Python/backend: **107 testes aprovados** (`107 passed`). Para executá-la no ambiente de release foi criado apenas um `frontend/dist` sintético temporário, porque o backend monta a pasta de assets no import; esse diretório foi removido após os testes e não entra nos artefatos.
- JSON de `package.json` e `package-lock.json`: válido.
- CSS alterado: balanceamento estrutural de chaves válido.
- Arquivos TS/TSX alterados: **0 diagnostics** na transpilação sintática com TypeScript 5.8.3.
- Backend, migrations, `.env`, banco, `node_modules`, `dist` e caches de build ficam fora do patch.

## Limitação do ambiente
`npm ci` não pôde restaurar as dependências porque o ambiente de geração não conseguiu acessar o npm registry (`EAI_AGAIN`). Por consequência, `npm test`, `npm run typecheck:e2e`, `npm run build` e a execução real do Playwright não foram marcados como aprovados neste ambiente. O cenário E2E de Radar Mobile foi adicionado ao release e deve ser executado normalmente em um ambiente com as dependências disponíveis.

Essa limitação é ambiental e foi mantida explícita: o release não declara build/browser test como aprovado sem tê-lo executado.
