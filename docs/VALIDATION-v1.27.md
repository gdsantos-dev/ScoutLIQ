# Validação — ScoutLIQ 1.27.0

## Executado

- 107 testes Python/backend;
- parser/transpilação sintática de todos os TS/TSX executáveis de `frontend/src`;
- testes isolados da lógica de contexto, preenchimento, fallback de templates e links externos;
- comparação byte a byte dos arquivos protegidos de backend/runtime contra a v1.26.0;
- validação estrutural de CSS/JSON;
- manifesto SHA-256 do FULL;
- aplicação real do patch v1.26.0 → v1.27.0 em cópia descartável;
- comparação da árvore source reconstruída pelo patch contra o FULL;
- teste de preservação de `.env` e banco sintético;
- teste de recusa de reaplicação e baseline divergente.

## Frontend completo

`npm ci`, `npm run build` e Playwright devem ser executados no ambiente de desenvolvimento/deploy com registry npm disponível. O release não considera esses comandos concluídos quando a instalação de dependências não fecha neste ambiente.

## Invariantes

A v1.27.0 não envia mensagens automaticamente, não cria contatos fictícios e não transforma abertura de WhatsApp/e-mail em atividade enviada. O registro comercial continua exigindo ação explícita do usuário.
