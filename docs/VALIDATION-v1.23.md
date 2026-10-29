# Validação v1.23.0

## Escopo protegido
- Backend: sem alteração de arquivo em relação à v1.22.0.
- Banco e migrations: sem alteração.
- Contratos de API: sem alteração.
- Score Engine, Research & Automation e regras comerciais: sem alteração.
- Desktop: tabelas e workspaces existentes permanecem como implementação desktop; as novas superfícies são ativadas por media query mobile.

## Cenários de interface cobertos pelo release
- Negociações usa composição vertical operacional no celular.
- Clientes usa lista mobile própria e não mostra a tabela desktop em viewport estreito.
- Sites / Entregas usa lista mobile própria com domínio, renovação, margem e alertas.
- Financeiro usa ledger mobile próprio para todas as quatro abas de movimentação.
- Filtros e tabs mantêm alvos adequados para touch e rolagem horizontal quando necessário.
- Fluxos existentes de contexto, detalhes, recebimento, edição e exclusão continuam usando os mesmos handlers.
- O cenário E2E adiciona uma verificação dedicada de Gestão Mobile em 390×844 e mantém a matriz responsiva já existente.

## Resultado executado na geração
- Arquivos TS/TSX funcionais alterados: transpilação sintática sem diagnostics.
- Suíte Python/backend: **107 testes aprovados** (`107 passed`). Foi usado somente um `frontend/dist` sintético temporário porque o backend monta a pasta de assets no import; esse diretório não entra no release.
- Backend e migrations comparados byte a byte com a v1.22.0: **0 arquivos de fonte divergentes**.
- O patch é aplicado em cópia descartável da v1.22.0 e comparado com o FULL da v1.23.0 no fechamento do release.

## Limitação do ambiente
A restauração completa das dependências frontend depende do npm registry. `npm ci --offline` falhou por pacote ausente no cache e a tentativa online não concluiu dentro da janela do ambiente. Por isso `npm test`, `npm run typecheck:e2e`, `npm run build` e Playwright não são declarados como aprovados sem execução real. O cenário E2E foi atualizado e deve ser rodado no ambiente de deploy com acesso normal ao registry.
