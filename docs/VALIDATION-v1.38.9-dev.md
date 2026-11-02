# Validação v1.38.9-dev

Estado intermediário: implementação em validação; PR deve permanecer em rascunho até conclusão dos checks.

Executado localmente em Windows, Python 3.12, Node 22, SQLite e PostgreSQL 17.11 portátil isolado. Dados e provedores sintéticos. Os resultados finais e links do CI serão consolidados após os jobs terminarem.

- 13 testes iniciais de confiabilidade aprovados.
- 27 testes focados no PostgreSQL aprovados após correção da migração 011.
- Três testes com processos reais aprovados (226,60 s): crash durante busca, crash durante investigação, start/stop/restart do supervisor; nenhuma duplicação de Lead ou outbox.
- 27 testes unitários frontend, TypeScript e build aprovados; npm audit: zero vulnerabilidades.
- pip-audit encontrou pytest 9.0.2 vulnerável; atualização para 9.0.3 e repetição: nenhuma vulnerabilidade conhecida.
- Regressões completas SQLite, PostgreSQL e Chromium em execução; CI remoto ainda não executado neste checkpoint.

Falhas intermediárias preservadas em artifacts/: comparação boolean/integer na migração 011; fixture PostgreSQL sem config_json/timezone (corrigida); restrições de sandbox e cluster encerrado entre sessões (não são aprovação de testes). Sem alteração de critérios comerciais para acomodar testes.

Não homologados: Docker da aplicação, Railway, infraestrutura de produção/HTTPS, provedores reais, Gmail/WhatsApp, dispositivos físicos, Safari, leitor de tela, resultados comerciais e restore de produção. Nenhum envio, deploy, merge ou banco pessoal alterado.
