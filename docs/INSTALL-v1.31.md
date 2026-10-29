# Instalação e atualização — ScoutLIQ 1.31.0

FULL e PATCH exclusivos para a base 1.30.0. Código-fonte sem banco, .env real, credenciais, node_modules ou arquivos de teste gerados. Histórico da 1.20 preservado separadamente.

## FULL

Requer Python 3.12+ e Node compatível com Vite 7. Extraia ScoutLIQ em uma pasta nova e execute na raiz:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
npm ci --prefix frontend
Copy-Item .env.example .env
npm run build --prefix frontend
python -m alembic upgrade head
python scripts/start.py
```

Edite o .env antes de iniciar: banco/credenciais próprios, origem exata, DEMO_SEED=false para operação. Não reutilize credenciais sintéticas. A revisão final é 020. O build deve preceder a importação da aplicação, que monta frontend/dist/assets.

## Worker persistente

No mesmo host e diretório, com o mesmo ambiente virtual, .env e DATABASE_URL do servidor web:

```powershell
python -m backend.research_worker
```

O processo deve permanecer ativo, gerenciado pelo supervisor do host. Não é iniciado automaticamente pelo navegador nem pelo comando web. Com SQLite, ambos precisam acessar o mesmo arquivo em volume persistente local. Réplicas em volumes diferentes não compartilham fila. A instalação em Railway/Docker e o supervisor 24/7 não foram homologados nesta entrega.

Configuração padrão:

```dotenv
RESEARCH_EXECUTION_MODE=worker
RESEARCH_LEASE_SECONDS=300
RESEARCH_MIN_INTERVAL_SECONDS=15
RESEARCH_DAILY_BUDGET=100
```

Orçamento diário UTC conta tarefas/tentativas, não requisições internas nem custo financeiro. O executor é global por banco; mínimo de 5 segundos entre tarefas, lease mínimo de 60 segundos, três tentativas com backoff. Não aumente concorrência esperando throughput distribuído. Veja ARCHITECTURE-v1.31.md.

Para legado explícito, pare web e worker, configure RESEARCH_EXECUTION_MODE=legacy em todos os processos e reinicie somente web. Nesse modo o browser volta a executar passos através do mesmo claim; o worker contínuo recusa iniciar. Nunca opere processos com modos diferentes sobre o mesmo banco.

## PATCH sobre 1.30.0

1. Pare web e worker. Faça backup consistente do banco com scripts/backup.py e guarde .env e fontes anteriores.
2. Extraia o PATCH fora da instalação. Faça preflight e depois aplique:

```powershell
python apply_release_patch.py --target C:\caminho\ScoutLIQ
python apply_release_patch.py --target C:\caminho\ScoutLIQ --apply
```

3. O aplicador valida hashes, recusa conflito antes de escrever e cria backup dos fontes afetados. Não aplique sobre 1.20, 1.29 ou uma base personalizada conflitante.
4. Instale requirements.lock, execute npm ci --prefix frontend, build e alembic upgrade head. Configure o worker; reinicie os dois processos. Verifique login, /api/health, dados existentes, ficha Operação e progresso de um lote controlado.

## Reversão e dados

O teste descartável 019 → 020 → 019 → 020 preserva evidências/rascunhos e registros centrais anteriores, mas downgrade remove metadados 020, políticas por destinatário e estado do executor. Para preservar integralmente o estado operacional, restaure backup consistente e código compatível. Nunca use downgrade como substituto do backup.

## Operação

Abra uma empresa e selecione Operação. Investigue ou registre observação com fonte/escopo; revise classificação e justificativa. Fatos livres em inglês/espanhol exigem tradução revisada. Prepare a estratégia disponível, destinatário, idioma e evidências. Edite e aprove o conteúdo. A condição de contato é registrada separadamente e nunca habilita envio nesta versão.

Pedidos de remoção por destinatário exato valem em outros leads da mesma conta/canal. Não há associação presumida entre e-mail e telefone. Registre cada canal abrangido pelo pedido. Políticas por destinatário persistem independentemente da exclusão de um lead.

## Validação local

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
npm run test --prefix frontend
npm run typecheck:e2e --prefix frontend
python scripts/start_e2e.py --port 8003
# Em outro terminal, na raiz:
$env:E2E_ORIGIN='http://localhost:8003'
$env:E2E_PYTHON=(Resolve-Path .venv\Scripts\python.exe).Path
npm run test:e2e --prefix frontend
```

O servidor E2E usa apenas data/e2e.db sintético; não exponha sua porta publicamente. Instale o navegador do Playwright se ausente. No Windows, TEMP/TMP podem ser definidos para uma pasta local gravável. Não use banco real para testes.

Envio oficial exige implementação futura: OAuth Gmail e armazenamento seguro/revogável de tokens, integração WhatsApp Business, verificação de destinatário/mercado/template/janela, revalidação de aprovação, outbox idempotente e webhooks autenticados/deduplicados. Inserir uma chave não ativa esses recursos. Consulte SECURITY-GATE-v1.31.md antes de qualquer deploy.
