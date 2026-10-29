# Validação — ScoutLIQ 1.26.0

## Executado no ambiente de geração

- suíte Python/backend: **107/107 testes passando**;
- backend + migrations + arquivos de dependência protegidos comparados byte a byte contra a v1.25.0;
- TypeScript/TSX de `frontend/src` e `frontend/e2e` analisados sintaticamente com o parser TypeScript;
- JSON de package/lock/webmanifest validado;
- CSS com estrutura de blocos balanceada;
- lógica da fila validada isoladamente para ação atrasada, de hoje, futura, primeiro contato derivado e exclusão de leads ganhos/perdidos;
- FULL validado por manifesto SHA-256;
- patch 1.25.0 → 1.26.0 validado em cópia descartável antes do release final.

## Frontend completo

O release tenta executar `npm ci`, `npm test`, typecheck/build e Playwright quando as dependências estão disponíveis. Caso o registry/cache não permita uma instalação completa, essa limitação é registrada no relatório JSON do release e a validação browser deve ser repetida no ambiente de desenvolvimento/deploy.

## Checklist visual recomendado

### Desktop

- Gerir clientes abre Ações em uma sessão iniciada pelo Radar;
- tabs Hoje / Atrasadas / Próximas não mudam layout ao trocar contagens;
- motivos de prioridade permanecem legíveis sem parecer badges decorativas;
- WhatsApp, telefone e e-mail só aparecem quando existe dado correspondente;
- Agir expande o registro/remarcação sem deslocamento lateral.

### Mobile

- cinco destinos do ambiente de gestão cabem na navegação inferior sem overflow horizontal;
- fila não gera scroll horizontal em 320–430 px;
- drawer de ação vira uma coluna touch-first;
- botões de registro têm alvo confortável;
- input de data respeita largura do viewport;
- Context Panel continua abrindo normalmente a partir da fila.

## Regras preservadas

A v1.26.0 não muda Score Engine, automações, regras de estágio, vendas, financeiro, autenticação, pesquisa, Radar ou persistência. A fila apenas compõe e aciona capacidades existentes.
