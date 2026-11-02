# v1.38.9-dev — Confiabilidade e preparação operacional

- CI com backend completo em SQLite e PostgreSQL, migrações, frontend, TypeScript, build, Chromium crítico/completo, auditorias e guarda de arquivos sensíveis.
- Instalação de testes com versões transitivas fixadas em requirements-dev.lock; psycopg 3.3.6 para PostgreSQL; pytest 9.0.3 corrige o aviso PYSEC-2026-1845 da versão 9.0.2.
- Migração 011 usa `IS TRUE` em vez de comparação booleano/integer, compatível com os dois bancos. A revisão permanece 033; nenhuma migração ou transformação de dados nova.
- Worker tolera falha de conexão também ao registrar heartbeat de erro e de encerramento. Mantém leases, fencing, orçamento, tentativas e executor existentes.
- Health checks retornam 503 seguro em indisponibilidade. Readiness verifica a revisão 033.
- Diagnóstico por CLI com estados agregados, esquema, worker, planos, retentativas, claims expiradas e orçamento; logs estruturados de falhas do worker/supervisor sem payloads.
- Testes com processos reais interrompem busca/investigação e validam recuperação sem efeitos duplicados; proxy de teste reproduz perda de conexão PostgreSQL e reconexão.
- Runbook de homologação reproduzível. Sem alteração comercial, Score, interface, deploy ou envio.

- Fixtures de CI usam o fuso da conta; E2E aguarda transições e respostas de controle antes de avaliar o estado. Nenhuma regra de validação ou acessibilidade foi desativada.
