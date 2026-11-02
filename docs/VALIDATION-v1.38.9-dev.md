# Validação v1.38.9-dev

Relatório de 02/11/2026. Dados, contas, credenciais e provedores de teste sintéticos; nenhum envio comercial, deploy, merge ou acesso a banco pessoal. O [PR #2](https://github.com/gdsantos-dev/ScoutLIQ/pull/2) contém os checks do commit mais recente. As evidências completas abaixo identificam seu próprio commit; reruns e ambientes não são somados como testes distintos.

## Resultados executados

[CI completo aprovado — 41369123566](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41369123566), código `ac20131a851e4d7c20b46dcb1fd7ddf5fa9f5654`: todos os 22 jobs aprovados (backend, PostgreSQL, frontend e 19 suítes de navegador).

| Verificação | Resultado | Evidência/escopo |
|---|---|---|
| Backend SQLite Linux | 624 aprovados, dois skips, zero falhas/erros | JUnit: 626 coletados, 228,775 s |
| Backend PostgreSQL Linux | 597 aprovados, 29 skips, zero falhas/erros | JUnit: 626 coletados, 255,916 s; role sem superuser/createdb/createrole |
| Frontend unitário | 27 aprovados em oito arquivos | Vitest |
| TypeScript / Vite | Aprovados | Instalação limpa por npm ci; tipo dos E2E incluído |
| Chromium completo | 79 aprovados em 19 suítes | Auth, busca, absorção, investigação, planejamento, operação diária, comercial, comunicação, UX, responsividade e Axe |
| Dependências | Nenhuma vulnerabilidade conhecida nas auditorias executadas | pip-audit requirements-dev.lock e npm audit |
| Higiene Git | Aprovada | diff --check e guarda de arquivos/padrões sensíveis |
| Backend SQLite Windows | 622 aprovados, dois skips | 1309,35 s; antes dos dois testes finais adicionais presentes no CI |
| Backend PostgreSQL Windows | 595 aprovados, 29 skips | 961,65 s; PostgreSQL 17.11 portátil isolado; mesma diferença de dois testes |
| Chrome Windows | 77 aprovações / duas falhas na rodada completa; dois retestes de planejamento aprovados após correção | Cobertura de todas as 19 suítes; a rodada inicial falha permanece explicitamente registrada |
| Processos reais | Aprovados | Kill durante busca/investigação, lease real, fencing, start/stop/restart, persistência; três testes focados em 226,60 s, também incluídos nas suítes completas |
| Perda de conexão PostgreSQL | Aprovada | Proxy loopback fecha conexões do worker real; processo sobrevive, reconecta e atualiza heartbeat, sem SQL/URL/senha no log |
| Backup/restore PostgreSQL local | Aprovado com dados sintéticos | pg_dump custom / pg_restore: 57 tabelas, revisão 033, relação lead/usuário e outbox vazia preservadas |

[Recibo estruturado](qa-v1.38.9-dev/results.json) contém contagens por suíte, durações e SHA-256 dos locks. Os relatórios completos do CI ficam nos artefatos do run (retenção de sete dias); artifacts/ e bancos locais permanecem ignorados e não publicados. Python 3.12, Node 22; Actions em Ubuntu 24.04; testes locais em Windows. O cluster portátil foi encerrado ao fim da validação, sem instalar serviço no Windows.

Os **29 skips PostgreSQL** pertencem exclusivamente aos dez módulos que usam sqlite3.backup: absorption (4), absorption_recovery (4), commercial_review (3), communication (2), followup (3), investigation (3), learning (2), location (1), opportunity (5), prospecting (2). Todos são obrigatórios no job SQLite. Os **dois skips SQLite** são a preservação de migração nativa PostgreSQL e a perda de conexão PostgreSQL. Não houve skip de contratos de negócio/isolamento para acomodar incompatibilidades.

## Defeitos encontrados e corrigidos

1. **Migração 011:** PostgreSQL rejeitava booleano comparado a inteiro. `in_pipeline IS TRUE` funciona nos dois bancos e preserva a transformação original. Revisão permanece 033; sem migração adicional.
2. **Worker em outage:** o heartbeat chamado pelo próprio tratamento de erro podia lançar nova exceção e encerrar o processo. Heartbeats de erro/encerramento agora são protegidos; retry, budgets e fencing existentes permanecem intactos.
3. **Health/readiness:** indisponibilidade agora retorna 503 genérico; readiness recusa revisão diferente de 033. Logs de startup informam a etapa sem imprimir SQL/credenciais.
4. **Dependência de teste:** pip-audit identificou PYSEC-2026-1845 no pytest 9.0.2; atualizado para 9.0.3, auditoria repetida e aprovada.
5. **Fixtures Linux:** date.today() usava UTC do runner, podendo enviar venda futura para conta America/Sao_Paulo. Fixtures usam o fuso da conta; bloqueio de venda futura no backend não mudou. Checkout limpo precisava criar artifacts/ antes de --basetemp.
6. **Axe durante transição:** experience auditava o fade de navegação. Trace mostrou opacidade intermediária. Agora aguarda opacity=1 e ausência de loading, mantendo regras Axe, animações e cores. Reteste local: três aprovados; CI completo acima: três aprovados.
7. **Planejamento no Chrome local:** a leitura do estado competia com POSTs de pausa/desativação. A fixture agora aguarda cada resposta pela ação exata, exige sucesso e estado correspondente, e verifica a UI antes da próxima operação. A primeira tentativa de wait capturava o POST de pausa por ser ampla demais; corrigida. Reteste em banco novo, porta 9871: dois aprovados (44,6 s Playwright / 46,3 s runner). Nenhuma alteração no motor de plano ou regras de autorização.

A última alteração de planejamento afeta somente sincronização do E2E e é coberta pela matriz crítica do commit final. A regressão completa de 19 suítes acima validou o mesmo código de aplicação. O workflow não repete checks ao converter draft em ready, pois PRs em draft já são testados; reexecução completa permanece disponível por label ci:full ou dispatch. A label usada nesta homologação pode ser removida ao encerrar a rodada completa, preservando os checks críticos automáticos.

## Histórico de execuções falhas

- [41367605087](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41367605087): frontend e oito suítes críticas aprovados; SQLite 602 aprovados, oito falhas, 12 erros de fixture, dois skips; PostgreSQL 586 aprovados, oito falhas, um erro de fixture, 29 skips. Causas: fuso e artifacts/ ausente, corrigidas acima.
- [41368310472](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41368310472): backend SQLite 624 aprovados e PostgreSQL 597 aprovados; suíte experience falhou durante fade; demais suítes aprovadas. Supersedida pelo run completo verde 41369123566.
- Windows: primeira rodada de planejamento falhou e causou falha de preparação do cenário seguinte; correção e reteste registrados acima. Não se classifica a primeira rodada como toda verde.
- Erros intermediários de ambiente: sandbox impediu rede/temp, cluster de testes encerrado entre sessões e primeira fixture PostgreSQL sem config_json/timezone. Foram corrigidos antes das execuções aprovadas; não contam como aprovação.
- A interrupção por limite de uso da revisão automática não executou a ação pendente; retomada posterior confirmou o estado Git e CI antes de continuar.

## Segurança e integridade

- `test_operational_autonomy`: reserva concorrente antes da rede, orçamento persistente, fencing de tentativa antiga, pausa/cancelamento, fonte alterada, autorização por objeto e encerramento de filhos do supervisor.
- `test_prospecting`: dois workers/um job, reserva atômica do plano, autorização atual, isolamento de contas, limites inválidos, CSRF, janela expirada e impossibilidade de zerar orçamento ao excluir rotina.
- `test_daily_operations`: IDs de outra conta, versões, políticas de contato, teto de investigação e claim expirada sem segundo item.
- `test_communication`: acesso cruzado, mass assignment/CSRF, expiração/revogação OAuth, idempotência, reserva antes da rede e recuperação sem reenvio após fronteira persistida, com adaptadores sintéticos.
- `test_reliability`: readiness rejeita schema antigo, 503 sem SQL, logs de migração sem secrets, paths/tokens proibidos e recusa de alvo PostgreSQL não isolado.

Não há novo endpoint de negócio, DTO ou upload. Diagnósticos detalhados ficam no CLI; health público retorna somente status. SQLAlchemy mantém queries parametrizadas; DDL de fixture usa apenas UUID gerado internamente. CI usa contents:read, sem secrets, sem persistir credenciais e sem pull_request_target; actions e imagem PostgreSQL fixadas por SHA/digest. Autenticação, autorização, CORS, CSRF, rate limits, políticas de destinatário e SSRF permanecem cobertos pela regressão existente. A guarda de repositório cobre caminhos e padrões conhecidos, não garante detectar todo formato possível de informação sensível. Não se declara auditoria exaustiva ou homologação HTTPS.

## Limitações e próximo passo

**Implementado e testado:** código, CI, SQLite, PostgreSQL sintético, processos, migrações, browser, diagnóstico e restore local. **Não homologado externamente:** imagem Docker da aplicação, Railway, produção/HTTPS, provedores reais, Gmail/WhatsApp, Safari, dispositivos físicos, leitores de tela, qualidade comercial e recuperação de desastre em produção. CI com PostgreSQL em container não homologa a imagem da aplicação.

Avisos conhecidos: Starlette/anyio deprecations, chunk de mapa Vite e arquivo redesign lento no Windows; nenhum foi ocultado ou convertido em aprovação falsa. Locks Python fixam versões transitivas, não hashes de distribuição.

Próximo passo: revisão humana de #2 e integração da base #1 conforme decisão do proprietário; depois verificar histórico antes de retarget para main. Homologação de host/TLS/backup/provedores requer ambiente e autorização próprios. Nenhum merge, deploy, serviço pago ou envio está autorizado por esta entrega.
