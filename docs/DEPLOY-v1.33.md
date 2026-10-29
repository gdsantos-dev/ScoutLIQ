# Deploy com worker no mesmo serviço

**Implementado e ensaiado localmente; Docker/Railway não homologados. Nenhum deploy ou banco de produção foi alterado.**

A estratégia SQLite usa um serviço, um volume `/data`, um servidor Uvicorn e um worker de pesquisa. Não há Redis, Celery ou PostgreSQL obrigatório. Web e worker recebem o mesmo ambiente e abrem o mesmo arquivo. Não executar réplicas independentes com cópias de SQLite.

## Inicialização

O comando padrão `python scripts/start.py` valida ambiente/volume, executa Alembic, faz bootstrap da primeira conta se necessário e supervisiona os dois filhos. `SCOUTLIQ_PROCESS_MODE=combined` e `RESEARCH_EXECUTION_MODE=worker` são o padrão. O bootstrap ocorre antes de ambos, evitando disputa pela primeira conta. O modo `web` mantém execução web isolada para hosts com supervisão própria; nesse caso o operador precisa iniciar o worker separadamente com o mesmo banco. Legacy exige modo web e não suporta rotinas comerciais.

Na imagem Docker, um bootstrap curto ajusta somente `/data` e os três arquivos SQLite conhecidos, rejeita symlinks e abandona grupos/UID/GID root antes de migrações e processos de aplicação. Os filhos executam como `scout` UID 10001. Não há chown recursivo. O caminho SQLite desta imagem é `/data/scoutliq.db`. Um volume existente em outro caminho não é migrado automaticamente.

| Variável | Produção |
|---|---|
| APP_ENV | production |
| APP_ORIGIN | origem HTTPS exata |
| DATABASE_URL | sqlite:////data/scoutliq.db |
| SCOUTLIQ_PROCESS_MODE | combined |
| RESEARCH_EXECUTION_MODE | worker |
| DEMO_SEED | false |
| ADMIN_EMAIL / ADMIN_PASSWORD | somente criação inicial; senha própria forte |
| RADAR_PROVIDER / RADAR_GEOAPIFY_API_KEY | fonte oficial configurada; chave apenas backend |
| SCOUT_BRAVE_SEARCH_API_KEY | opcional, apenas backend |

O host fornece `PORT`. Credenciais reais ficam em variáveis privadas. MapTiler é uma chave pública de mapa já prevista na base, restrita por origem; não confundir com secrets de backend. O modo produção exige as restrições de origem/cookies/headers existentes. Configure cotas de [AUTONOMY-v1.33.md](AUTONOMY-v1.33.md) conforme o contrato da conta do provedor.

## Saúde e recuperação

- `/api/health`: web existente; `/api/health/worker`: disponibilidade mínima, sem IDs, leads ou erros internos; `/api/health/ready`: banco + worker no modo combinado.
- `python -m backend.worker_health`: verificação independente, exit 0/1. A CLI lê o banco configurado; não é um worker.
- Heartbeat por UUID de processo. O supervisor observa seu próprio worker, sem aceitar que outro worker saudável o mascare. Inativo precisa renovar em até 30 s. Em trabalho, a saúde vale até o prazo do token, padrão 300 s. O loop renova a cada três segundos, sem fingir progresso numa tarefa travada.
- Após 60 s de tolerância inicial, heartbeat inválido encerra o conjunto. Morte de qualquer filho também encerra seu irmão, exit 1; Railway tem política ON_FAILURE, máximo cinco reinícios. Não há laço interno infinito escondendo falha persistente.
- SIGTERM/SIGINT e SIGBREAK no Windows pedem parada. Filhos têm até 20 s antes de término forçado. Uma tarefa interrompida pode repetir leitura após vencer o lease; token antigo não confirma efeitos no CRM. Reserva/contador permanece.

O Railway usa healthcheck para a entrada de um deploy, não para supervisão contínua; por isso existe watchdog local. Um volume por serviço e ausência de réplicas com volume tornam essa arquitetura adequada à instalação SQLite atual. Redeploy com volume pode implicar indisponibilidade breve; não é uma arquitetura de alta disponibilidade. Referências verificadas: [volumes](https://docs.railway.com/volumes/reference), [healthchecks](https://docs.railway.com/deployments/healthchecks), [reinício](https://docs.railway.com/deployments/restart-policy).

## Antes da homologação

Faça backup SQLite consistente usando `scripts/backup.py`, copie-o para local privado fora do volume e teste restauração. Valide permissões reais do mount, migração 022, login, CSRF, HTTPS, healthcheck, encerramento/reinício, persistência de uma rotina autorizada, orçamento e comportamento com fonte indisponível. Não confunda fixtures locais com prova de cobertura, latência, custo externo ou operação 24/7. Migração PostgreSQL não foi proposta/executada; exigiria plano específico e autorização.
