# Infraestrutura e homologação — v1.38.9-dev

## Arquitetura preservada

O supervisor `scripts/start.py` migra e faz bootstrap antes de iniciar web e worker. Um filho encerrado ou heartbeat vencido encerra o serviço: o host deve reiniciar o grupo. Não há segundo executor nem reinício sem limite dentro do app. O worker mantém a claim atômica, lease mínima de 60 segundos, fencing e ledger persistente. Reads externos podem repetir após crash; efeitos comerciais já confirmados não podem duplicar. Uma operação reservada antes do crash continua consumindo orçamento: não reembolsar automaticamente, pois o provedor pode tê-la recebido.

A falha de conexão agora é tolerada durante heartbeat normal, de erro e final. O loop tenta novamente após três segundos; abertura de conexão PostgreSQL tem timeout de cinco segundos e pool_pre_ping. O supervisor ainda pode encerrar um worker degradado após seu prazo, exigindo restart do host. Esses limites não equivalem a um timeout universal de queries.

Não há alteração no Score 3.0, seleção comercial, contatos, autorização ou UI. Migração 033 permanece obrigatória. A correção histórica de SQL da 011 é necessária para instalações PostgreSQL novas; bancos já migrados não repetem essa migração.

## Ambiente e instalação limpa

Python 3.12, Node 22, Git, PostgreSQL 17 ou SQLite. Instale a partir do checkout e dos locks:

```sh
python -m venv .venv
# Ative .venv (Windows: .venv/Scripts/Activate.ps1; Linux: source .venv/bin/activate)
python -m pip install -r requirements.lock
cd frontend
npm ci
npm run build
cd ..
```

Para testes: `python -m pip install -r requirements-dev.lock`. O lock fixa dependências transitivas, mas não hashes de distribuição; CI usa runners limpos. Não copiar ambientes virtuais de releases. Copiar `.env.example` somente se não existir `.env` e preencher localmente. Nunca versionar esse arquivo ou logs de configuração.

Configuração sintética: APP_ENV=test, APP_ORIGIN=http://localhost:8000, ADMIN_EMAIL de teste, ADMIN_PASSWORD exclusiva >=12 caracteres, DEMO_SEED=false, EMAIL_MODE=memory, RESEARCH_EXECUTION_MODE=worker, SCOUTLIQ_PROCESS_MODE=combined. Não preencher credenciais de provedores. Produção exige configuração própria, HTTPS e autorização fora deste ciclo.

DATABASE_URL aceita `postgresql+psycopg://` e normaliza `postgresql://`/`postgres://`. Encode corretamente caracteres reservados de usuário/senha. Defina via secret manager ou arquivo local protegido; não use senha em argumentos de shell. Instâncias remotas futuras devem validar TLS/certificado (`sslmode=verify-full`) e restringir rede. Não apontar testes a Railway ou bancos pessoais.

PostgreSQL de teste: crie banco com prefixo `scoutliq_test_`, em loopback, com role NOSUPERUSER NOCREATEDB NOCREATEROLE. Ela deve poder criar schemas apenas nesse banco descartável. O bootstrap administrativo separado termina antes dos testes. `scripts/ci_postgres.py` só executa com GITHUB_ACTIONS=true e cria o banco descartável do serviço CI; suas senhas literais são exclusivamente sintéticas. Em homologação futura separar a role de migração/DDL da role de runtime/DML conforme política do host; o projeto não provisiona essas permissões automaticamente.

Para criar o alvo local em uma instância descartável já iniciada, conecte como administrador local pelo psql e execute (somente se os nomes ainda não existirem):

```sql
CREATE ROLE scoutliq_tests LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password scoutliq_tests
CREATE DATABASE scoutliq_test_local OWNER scoutliq_tests;
```

O comando psql `\password` solicita a senha sem colocá-la no histórico SQL. Restrinja listen_addresses a loopback e pg_hba.conf ao banco/role de teste com SCRAM; não use trust para acesso remoto. Defina SCOUT_TEST_POSTGRES_URL localmente e rode pytest. A própria fixture cria/remove somente seu schema UUID. Para reproduzir o ambiente Linux sem provisionamento manual, execute o workflow do PR, que contém o serviço PostgreSQL efêmero e seu bootstrap completo.

## Inicialização e diagnóstico

```sh
python -m alembic upgrade head
python scripts/start.py
# Em outra sessão no mesmo ambiente:
python -m backend.diagnostics
python -m backend.worker_health
```

`/api/health`: conectividade DB. `/api/health/worker`: heartbeat vivo. `/api/health/ready`: revisão 033 e, em combined, worker vivo. Retornam somente status, 200/503. Não expõem tabela, URL, erro SQL ou detalhes de contas.

O diagnóstico é CLI do operador, não endpoint público. Retorna revisão esperada/aplicada, contagens por estado de buscas/investigações/planos, motivos fixos de espera de planos ativos, retry pendente, claims de investigação expiradas, slot/intervalo e orçamento do executor. Readiness esperado deve ser atualizado junto de uma migração futura. Estados `error`/`partial` exigem revisão; `paused`/`cancelled` não autorizam retomada automática. Os detalhes por oportunidade continuam nas telas autenticadas existentes.

Eventos JSON `worker_cycle_failed`, `heartbeat_unavailable`, `startup_failed`, `child_exited`, `worker_stale` não incluem exceções, credenciais ou dados comerciais. `startup_failed.state` identifica configuration/migration/bootstrap. O supervisor suprime stdout/stderr da migração para impedir payloads SQL em logs gerais; para investigar, execute Alembic em terminal protegido e não publique saída bruta. Não há telemetria externa.

## Falhas e recuperação

| Sintoma | Procedimento |
|---|---|
| readiness 503, migration_required | Pare a entrada de trabalho; backup; confirme revisão e rode Alembic com a role apropriada. Não apagar tabelas. |
| database unavailable | Confira serviço, rede, autenticação, TLS e permissões sem imprimir DATABASE_URL; aguarde reconexão. |
| worker stale/child exited | Inspecione eventos, restaure dependência e reinicie o grupo pelo host. Não inicie executores auxiliares. |
| claim expirada | Permita recuperação após lease; o token antigo não pode gravar. Reservas anteriores permanecem contabilizadas. |
| retry_pending | Aguarde backoff e disponibilidade; falhas terminais/limite de tentativas exigem revisão. |
| plano pausado/autorização alterada | Revisar e autorizar na interface existente; nunca alterar estado diretamente no banco. |
| orçamento esgotado | Aguarde a janela apropriada; não zerar ledger para forçar execução. |
| downgrade bloqueado | Preserve dados. Restore em ambiente separado a partir de backup validado; nunca remover registros para forçar downgrade. |

## Backup e recuperação

Não misture backups SQLite e PostgreSQL. Antes de atualização operacional, pare web/worker e mantenha backup fora do repositório, criptografado e com acesso restrito. Para SQLite use a API de backup consistente existente (`scripts/backup.py`, consulte seu help) ou o procedimento INSTALL v1.38.7; nunca copiar somente o arquivo DB enquanto WAL está ativo.

PostgreSQL: usar pg_dump/pg_restore da versão compatível. Configure PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSFILE local com permissões restritas (0600 no Unix; ACL do usuário no Windows), sem senha na linha de comando. Exemplo, com destinos exclusivamente novos e descartáveis:

```sh
pg_dump --format=custom --no-owner --file=backup-protegido.dump
# Criar previamente um banco NOVO de recuperação; não usar --clean contra o banco original.
pg_restore --exit-on-error --no-owner --no-privileges --dbname=scoutliq_restore_test backup-protegido.dump
```

Depois compare revisão, contagens, relações e resultados conhecidos, execute diagnóstico e smoke autenticado sem provedores. Só uma restauração efetivamente executada comprova o backup. Neste ciclo houve uma restauração sintética local PostgreSQL 17.11: 57 tabelas, revisão 033, relação lead/usuário e outbox vazia preservadas. Não é homologação de recuperação de produção. O teste de migração deste ciclo comprova preservação 032→033 e recusa de downgrade destrutivo; não equivale a homologação de disaster recovery em produção.

## Reproduzir testes

```sh
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
python -m pytest -q --basetemp artifacts/pytest-local
python scripts/check_repository.py
python -m pip_audit -r requirements-dev.lock --no-deps --disable-pip
cd frontend
npm test
npm run typecheck:e2e
npm run build
npm audit
npx playwright install chromium
cd ..
python scripts/validate_browser.py --group critical --port 9700
python scripts/validate_browser.py --group full --port 9800
```

Localmente o runner usa Chrome instalado; em CI usa Chromium do lock Playwright. Para usar Chromium também localmente, defina CI=true. Cada port precisa ser nova pois o runner recusa reutilizar o DB sintético. Evidências e dados ficam em artifacts/ e data/, ignorados. Em Windows com restrição de temp, TEMP/TMP podem apontar para uma pasta nova em artifacts/.

Para PostgreSQL, defina SCOUT_TEST_POSTGRES_URL em sessão protegida com driver explícito `postgresql+psycopg`, loopback e DB `scoutliq_test_*`. Rode o mesmo pytest. A fixture cria um schema UUID novo e o remove ao final, sem tocar em public. URL com query e host remoto é recusada. Dez módulos de migração baseados em sqlite3.backup são específicos de SQLite e permanecem obrigatórios no job SQLite. PostgreSQL executa os contratos de negócio, concorrência, isolamento e preservação de migração nativa. Um proxy loopback descartável corta as conexões apenas do worker de teste; não altera firewall ou banco compartilhado.

## GitHub Actions

`.github/workflows/ci.yml`: PRs e pushes para main; execução manual; label `ci:full` no PR ativa todas as 19 suítes, contra oito críticas no padrão. Dispatch só fica disponível normalmente depois que o workflow existe na branch padrão. Matriz limitada a quatro navegadores simultâneos; build é produzido uma vez e reutilizado. PR em draft já executa os checks; converter para ready não dispara outra execução idêntica. Não há merges ou deploy automáticos. Jobs independentes: SQLite, PostgreSQL 17 efêmero, frontend e navegador. PostgreSQL é testado com role não superuser. Actions e imagem PostgreSQL fixadas por SHA/digest. Token contents:read; checkout sem persistir credenciais; nenhum pull_request_target ou segredo real. Artefatos sintéticos: relatórios até sete dias, build por um dia. Não enviar DBs ou logs brutos de runtime.

Referências: [segurança de Actions](https://docs.github.com/en/actions/reference/security/secure-use), [PostgreSQL Windows](https://www.postgresql.org/download/windows/), [instalação psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html).

## Impedimentos de deploy

CI obrigatório falho, segredo/dado real detectado, regressão de isolamento/idempotência, revisão divergente, restore não validado, configuração insegura de TLS/cookies/origins, credenciais/contato sem autorização ou runtime/host ainda não homologado impedem deploy. Dockerfile e Railway existentes são referências de infraestrutura, não evidência de deploy. CI com serviço PostgreSQL não homologa a imagem da aplicação, Railway, HTTPS, MFA externo, provedores ou resultados comerciais reais. Este ciclo não autoriza nenhum deles.
