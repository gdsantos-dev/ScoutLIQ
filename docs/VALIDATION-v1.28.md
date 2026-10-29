# Validação — ScoutLIQ 1.28.0

## Executado

- 107/107 testes Python/backend com `TZ=America/Recife`;
- parser/transpilação sintática de 40 arquivos TS/TSX executáveis de `frontend/src`, sem diagnostics de sintaxe;
- testes isolados da lógica de inteligência do histórico: cadência de ganho, etapa anterior à perda, readiness da amostra e diferença observada de padrões;
- comparação byte a byte de 58 arquivos protegidos de backend/runtime contra a v1.27.0: 0 diferenças;
- validação estrutural do CSS e JSON;
- manifesto SHA-256 do FULL;
- aplicação real do patch v1.27.0 → v1.28.0 em cópia descartável;
- comparação da árvore source reconstruída pelo patch contra o FULL;
- preservação de `.env` e banco sintético;
- recusa de reaplicação e de baseline divergente.

## Observação de fuso nos testes

O primeiro `pytest` foi executado depois da virada do dia em UTC enquanto Recife ainda estava no dia anterior. Oito casos antigos que usam `date.today()` no próprio teste foram rejeitados pela regra de data futura da aplicação. Repetindo a suíte com `TZ=America/Recife`, coerente com o fuso do cenário testado, os 107 testes passaram. Nenhum arquivo de backend foi alterado para contornar esse comportamento.

## Frontend completo

A tentativa de `npm ci --ignore-scripts --prefer-offline --no-audit --no-fund` não concluiu no ambiente de geração por timeout. Por isso `npm run build`, Vitest completo e Playwright não são declarados como executados nesta release. A limitação é de instalação de dependências no ambiente; os arquivos TypeScript alterados foram validados por transpilação sintática e a lógica nova foi exercitada isoladamente.

## Invariantes

A v1.28.0 não cria probabilidade de fechamento, não altera Opportunity Score, não classifica pessoas, não dispara ações comerciais e não inventa dados ausentes. As comparações expõem tamanho da amostra e são apresentadas como padrões descritivos, não causalidade.
