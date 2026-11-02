# ScoutLIQ — Handoff v1.38.9-dev

## Fonte e continuidade

Repositório: https://github.com/gdsantos-dev/ScoutLIQ, intencionalmente público. Checkout canônico: github/ScoutLIQ. ZIPs e work/ são históricos; não copiá-los sobre o Git.

Branch deste ciclo: `v1.38.9-confiabilidade`. [PR #2](https://github.com/gdsantos-dev/ScoutLIQ/pull/2), dependente de `v1.38.8-operacao-diaria` enquanto #1 permanece aberto. Base funcional: `ab9bb3b6f2a0f9c4eaa387c0b0abae990b22e1d8`, sincronizada com o HEAD de #1. Main não recebeu merge. Não renomear branches codex históricas; próximos ciclos usam `v<versao>-<funcao>` conforme CONTRIBUTING.

## Implementado

CI com instalação por locks, backend completo SQLite/PostgreSQL, migrações, frontend, TypeScript, Vite, Chromium crítico/completo, auditorias e guarda de arquivos sensíveis. Actions fixadas por SHA, serviço PostgreSQL por digest, permissões mínimas e sem credenciais reais.

Driver psycopg 3.3.6 e normalização de DATABASE_URL. Migração 011 corrigida para booleanos PostgreSQL; a revisão continua **033**, sem nova migração. Worker tolera indisponibilidade do banco inclusive no heartbeat de falha/encerramento. Health checks seguros e readiness com revisão explícita; diagnóstico agregado por CLI e eventos estruturados de inicialização/recuperação. Não há novo executor, Score, regra comercial, dashboard ou redesign.

## Validação e evidências

[CI completo aprovado](https://github.com/gdsantos-dev/ScoutLIQ/actions/runs/41369123566), código `ac20131a851e4d7c20b46dcb1fd7ddf5fa9f5654`: 624 testes SQLite (dois skips exclusivos de PostgreSQL), 597 PostgreSQL (29 skips exclusivos de backup SQLite), 27 unitários frontend e 79 Chromium em 19 suítes. Instalação limpa Linux, TypeScript, build, pip-audit e npm audit aprovados. Os checks do PR registram a validação do commit mais recente; o relatório identifica cada execução, sem somar reruns como testes distintos.

Windows local: regressão SQLite 622 aprovados/dois skips e PostgreSQL 595 aprovados/29 skips, antes dos dois testes adicionais validados no CI. Testes de processo real cobrem kill durante busca e investigação, lease vencida, token obsoleto, ausência de duplicação/outbox, start/stop/restart e persistência. PostgreSQL inclui perda real de conexão e reconexão; backup/restore sintético preservou 57 tabelas e revisão 033. O cluster portátil foi encerrado depois dos testes. Artefatos locais e bancos sintéticos continuam ignorados.

Resultados, falhas intermediárias, retestes e limites: [VALIDATION](docs/VALIDATION-v1.38.9-dev.md), [recibo JSON](docs/qa-v1.38.9-dev/results.json). Instalação, configuração, migrações, backup, diagnóstico, falhas comuns e CI: [OPERATIONS](docs/OPERATIONS-v1.38.9-dev.md). Mudanças: [CHANGELOG](docs/CHANGELOG-v1.38.9-dev.md). Contratos funcionais preservados: [arquitetura v1.38.8](docs/ARCHITECTURE-v1.38.8-dev.md) e [v1.38.7](docs/ARCHITECTURE-v1.38.7-dev.md).

## Limites e próximos passos

Não homologados: Docker da aplicação, Railway, produção/HTTPS, provedores reais, Gmail/WhatsApp, Safari, dispositivos físicos, leitores de tela e resultados comerciais. O serviço PostgreSQL do CI não homologa a infraestrutura final. Permanecem avisos de depreciação Starlette/anyio e chunk de mapa do Vite, sem falha nos checks. Locks fixam versões, não hashes de distribuições Python; guarda de secrets cobre padrões conhecidos, não garante identificação de qualquer dado sensível possível.

Revisar #2; integrar #1 somente por decisão humana. Depois verificar o histórico antes de mudar a base de #2 para main. Planejar homologação de host/HTTPS, restauração e provedores com credenciais e autorizações próprias. Não houve merge, deploy, envio comercial ou alteração de banco pessoal. Nenhuma dessas ações está autorizada por um push.
