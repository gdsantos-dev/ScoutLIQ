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

## Cobertura de segurança e integridade

- `test_operational_autonomy`: reserva concorrente antes da rede, orçamento persistente, fencing de tentativa antiga, pausa/cancelamento, fonte alterada, autorização por objeto e encerramento de filhos do supervisor.
- `test_prospecting`: dois workers/um job, reserva atômica do plano, autorização atual, isolamento de contas, limites inválidos, CSRF, janela expirada e impossibilidade de zerar orçamento ao excluir rotina.
- `test_daily_operations`: IDs de outra conta, seleção persistente com versões, bloqueios de contato, teto de investigação e claim expirada sem segundo item.
- `test_communication`: acesso cruzado, mass assignment/CSRF, expiração/revogação de OAuth, idempotência, reserva antes da rede e recuperação sem reenvio após fronteira persistida. Adaptadores sintéticos, sem mensagens reais.
- `test_reliability`: readiness recusa esquema antigo, respostas públicas 503 sem SQL, logs de migração sem segredos, guarda de paths/tokens e recusa de alvos PostgreSQL não isolados.

Revisão da mudança: nenhum novo endpoint de negócio, DTO ou upload; diagnósticos detalhados ficam no CLI, health público retorna apenas status. Consultas agregadas usam SQLAlchemy; o único identificador dinâmico de DDL nas fixtures é UUID gerado internamente, nunca entrada do usuário. O novo CI usa permissions contents:read, sem secrets, sem persistir credenciais e sem pull_request_target. A guarda de repositório cobre padrões conhecidos e caminhos proibidos, não substitui revisão humana de dados/segredos de formato desconhecido. Autenticação, autorização, CORS, CSRF, rate limits, políticas de destinatário, proteção SSRF e demais contratos são preservados e exercitados pela regressão existente; não se declara auditoria exaustiva de segurança ou homologação HTTPS.

## Primeira execução remota (falha corrigida, não contabilizada como aprovação)

[Actions 41367605087](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41367605087): frontend e oito suítes críticas aprovados. SQLite: 602 aprovados, oito falhas, 12 erros de fixture, dois skips; PostgreSQL: 586 aprovados, oito falhas, um erro de fixture, 29 skips. Falhas de venda provinham de date.today() no UTC do runner, enquanto a conta sintética opera em America/Sao_Paulo. As fixtures agora calculam sua data no fuso da conta, sem mudar o bloqueio de venda futura. Erros tmp_path provinham de artifacts/ ausente no checkout limpo; workflow agora cria o diretório explicitamente.

Backup/restore local PostgreSQL 17.11: pg_dump custom + DROP apenas do schema UUID criado pelo teste + pg_restore no mesmo banco descartável. Revisão 033, 57 tabelas, relação lead/usuário sintética e outbox vazia preservadas. Nenhum dado pessoal. Essa evidência não homologa restore de produção.

## Regressão Linux após correções de portabilidade

[Actions 41368310472](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41368310472), código `ee1f64f3a484826854c028a643af74606bf59060`: SQLite 624 aprovados / dois skips (252,494 s); PostgreSQL 597 aprovados / 29 skips (257,342 s); zero falhas/erros nos dois JUnit. Ambos incluem os testes de processos reais; o job PostgreSQL inclui perda real de conexão via proxy e reconexão. Frontend e auditorias também aprovados.

Os 29 skips PostgreSQL pertencem exclusivamente aos dez módulos que usam sqlite3.backup: absorption (4), absorption_recovery (4), commercial_review (3), communication (2), followup (3), investigation (3), learning (2), location (1), opportunity (5), prospecting (2). Todos rodam no job SQLite. Seus dois skips são os testes exclusivos de PostgreSQL (migração nativa e conexão interrompida).

A matriz completa expôs uma corrida no teste experience: o trace mostra page-view ainda em fade quando Axe calculou contraste. O teste agora aguarda opacity=1 e ausência de loading, como a suíte redesign existente. Não houve alteração em tokens, animações, escopo ou regras Axe. A confirmação no CI do ajuste está pendente neste checkpoint.

Regressão local PostgreSQL: 595 aprovados / 29 skips em 961,65 s, antes da adição dos dois testes finais de readiness/startup. Estes passaram no job Linux final acima. Fixture de API e confiabilidade: 43 aprovados após correção de fuso.
