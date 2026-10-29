# Validação — ScoutLIQ 1.29.0

## Executado

- 107/107 testes Python/backend com `TZ=America/Recife`;
- comparação byte a byte de 66 arquivos protegidos de backend/runtime contra a v1.28.0: 0 diferenças;
- parser TypeScript em 43 arquivos `.ts`/`.tsx` executáveis: 0 erros sintáticos;
- compilação isolada de `ecosystemBridge.ts` com TypeScript global;
- assertions determinísticas do ORLIQ Bridge para schema, recebível, opt-out de contato, exclusão de notas internas e naming do arquivo;
- validação estrutural de JSON/CSS;
- geração de manifest SHA-256 do FULL;
- dry-run e aplicação real do patch v1.28.0 → v1.29.0 em cópia descartável;
- comparação do resultado do patch com o FULL por hashes;
- preservação de `.env` e banco sintético durante o teste do patch;
- teste de recusa de reaplicação e de baseline com alteração local.

## Frontend completo

`npm ci` não concluiu no ambiente de geração por timeout de acesso ao registry. Por isso esta validação **não declara** `npm run build`, suíte Vitest completa ou Playwright como executados. A validação browser deve ser repetida no ambiente de deploy com dependências instaladas.

## Segurança e escopo

- nenhuma migration nova;
- nenhum backend, endpoint ou schema existente alterado;
- nenhum token ou segredo é salvo pelo Bridge;
- exportação exige ação explícita do usuário;
- contatos são opt-in;
- notas internas de leads não entram no `orliq.bridge` v1;
- valores monetários permanecem em centavos com moeda explícita;
- o perfil DashLIQ é um contrato de handoff, não uma alegação de sincronização automática já existente.
